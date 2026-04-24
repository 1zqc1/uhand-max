/*
 * uhand - 机械手控制程序
 */
#include <FastLED.h>
#include <Servo.h>
#include <avr/wdt.h>

// 引脚
#define I2C_SDA 18
#define I2C_SCL 19
#define I2C_ADDR 0x77
const uint8_t SVP[6] = {7, 6, 5, 4, 3, 2};
#define BUZZER 11
#define RGB 13

// 参数
#define DMIN 50
#define DMAX 500

// 模式
enum M { O = 1, C, A, H, P, G, F, R, M };

// 状态
static uint8_t mode = M;
static uint16_t dist = 500;
static int16_t ft[5], fc[5];
static uint32_t t_servo = 0, t_sensor = 0;
static CRGB led;
static Servo sv[6];

// ========== I2C ==========
static void i2c_start(void) {
    pinMode(I2C_SDA, OUTPUT); pinMode(I2C_SCL, OUTPUT);
    digitalWrite(I2C_SDA, HIGH); digitalWrite(I2C_SCL, HIGH);
    delayMicroseconds(10);
    digitalWrite(I2C_SDA, LOW); digitalWrite(I2C_SCL, LOW);
}

static void i2c_stop(void) {
    pinMode(I2C_SDA, OUTPUT); digitalWrite(I2C_SDA, LOW);
    digitalWrite(I2C_SCL, HIGH); delayMicroseconds(10);
    pinMode(I2C_SCL, INPUT_PULLUP); delayMicroseconds(10);
    pinMode(I2C_SDA, INPUT_PULLUP);
}

static bool i2c_wr(uint8_t b) {
    for (int8_t i = 7; i >= 0; i--) {
        pinMode(I2C_SDA, OUTPUT); digitalWrite(I2C_SDA, (b >> i) & 1);
        delayMicroseconds(10);
        pinMode(I2C_SCL, INPUT_PULLUP);
        uint32_t t = micros(); while (!digitalRead(I2C_SCL) && micros() - t < 3000);
        delayMicroseconds(10);
        pinMode(I2C_SCL, OUTPUT); digitalWrite(I2C_SCL, LOW);
    }
    pinMode(I2C_SDA, INPUT_PULLUP); pinMode(I2C_SCL, INPUT_PULLUP);
    uint32_t t = micros(); while (!digitalRead(I2C_SCL) && micros() - t < 3000);
    delayMicroseconds(10);
    bool ack = !digitalRead(I2C_SDA);
    digitalWrite(I2C_SCL, LOW); delayMicroseconds(20);
    return ack;
}

static uint8_t i2c_rd(bool ack) {
    uint8_t b = 0;
    for (int8_t i = 7; i >= 0; i--) {
        pinMode(I2C_SDA, INPUT_PULLUP); pinMode(I2C_SCL, INPUT_PULLUP);
        uint32_t t = micros(); while (!digitalRead(I2C_SCL) && micros() - t < 3000);
        delayMicroseconds(10);
        if (digitalRead(I2C_SDA)) b |= (1 << i);
        pinMode(I2C_SCL, OUTPUT); digitalWrite(I2C_SCL, LOW);
        delayMicroseconds(10);
    }
    pinMode(I2C_SDA, OUTPUT); digitalWrite(I2C_SDA, ack ? LOW : HIGH);
    delayMicroseconds(10);
    pinMode(I2C_SCL, INPUT_PULLUP);
    uint32_t t = micros(); while (!digitalRead(I2C_SCL) && micros() - t < 3000);
    delayMicroseconds(10);
    pinMode(I2C_SCL, OUTPUT); digitalWrite(I2C_SCL, LOW);
    delayMicroseconds(20); pinMode(I2C_SDA, INPUT_PULLUP);
    return b;
}

// ========== 超声波 ==========
static int us_read(void) {
    pinMode(I2C_SDA, INPUT_PULLUP); pinMode(I2C_SCL, INPUT_PULLUP);
    delayMicroseconds(50);
    i2c_start();
    if (!i2c_wr(I2C_ADDR << 1)) { i2c_stop(); return -1; }
    if (!i2c_wr(0x00)) { i2c_stop(); return -1; }
    i2c_stop();
    delayMicroseconds(20000);
    i2c_start();
    if (!i2c_wr((I2C_ADDR << 1) | 1)) { i2c_stop(); return -1; }
    uint8_t b1 = i2c_rd(true), b2 = i2c_rd(false);
    i2c_stop();
    pinMode(I2C_SDA, INPUT_PULLUP); pinMode(I2C_SCL, INPUT_PULLUP);
    uint16_t d = (b2 << 8) | b1;
    return (d >= 10 && d <= 4000) ? d : -1;
}

// ========== 舵机 ==========
static void servo_set(uint8_t t, uint8_t i, uint8_t m, uint8_t r, uint8_t p) {
    ft[0] = t; ft[1] = i; ft[2] = m; ft[3] = r; ft[4] = p;
}

static void servo_update(void) {
    if (millis() - t_servo < 14) return;
    t_servo = millis();
    for (uint8_t i = 0; i < 5; i++) {
        int16_t d = ft[i] - fc[i];
        if (d) fc[i] += d / 4;
        sv[i].write(fc[i]);
    }
    sv[5].write(90);
}

// ========== RGB ==========
static void rgb_update(void) {
    uint8_t r = 0, g = 0;
    if (dist > 350) g = 255;
    else if (dist > 150) { r = map(dist - 150, 0, 200, 0, 255); g = 255; }
    else { r = 255; g = map(150 - dist, 0, 150, 0, 255); }
    led.r = r; led.g = g; led.b = 0; FastLED.show();
}

// ========== 自动模式 ==========
static void auto_update(void) {
    if (millis() - t_sensor < 50) return;
    t_sensor = millis();
    int d = us_read();
    if (d > 0) dist = constrain(d, DMIN, DMAX);
    float ratio = (float)(dist - DMIN) / (DMAX - DMIN);
    float grip = 1.0f - pow(ratio, 0.8f);
    servo_set(grip * 180, (1 - grip) * 180, (1 - grip) * 180, (1 - grip) * 180, (1 - grip) * 180);
    rgb_update();
}

// ========== 命令 ==========
static void handle(char c) {
    Serial.print("CMD:");
    switch (c) {
        case 'O': Serial.println("OPEN"); mode = O; servo_set(0, 180, 180, 180, 180); break;
        case 'C': Serial.println("CLOSE"); mode = C; servo_set(180, 0, 0, 0, 0); break;
        case 'A': Serial.println("AUTO"); mode = A; break;
        case 'M': Serial.println("MANUAL"); mode = M; servo_set(0, 180, 180, 180, 180); break;
        case 'H': Serial.println("HANDSHAKE"); mode = H; servo_set(90, 120, 150, 160, 170); break;
        case 'P': Serial.println("PINCH"); mode = P; servo_set(30, 30, 180, 180, 180); break;
        case 'G': Serial.println("GRIP"); mode = G; servo_set(180, 0, 0, 0, 0); break;
        case 'F': Serial.println("POINT"); mode = F; servo_set(120, 180, 60, 60, 60); break;
        case 'R': Serial.println("RELAX"); mode = R; servo_set(0, 180, 180, 180, 180); break;
        case '?': Serial.println("QUERY"); Serial.print("DIST:"); Serial.println(dist); return;
        default: Serial.println("UNKNOWN"); return;
    }
    Serial.print("MODE:"); Serial.println(mode);
}

// ========== setup ==========
void setup() {
    wdt_enable(WDTO_8S);
    Serial.begin(9600);
    Serial.println("=== START ===");

    for (uint8_t i = 0; i < 6; i++) sv[i].attach(SVP[i], 500, 2500);
    Serial.println("Servos OK");

    FastLED.addLeds<WS2812, RGB, GRB>(&led, 1);
    led = CRGB(0, 100, 0); FastLED.show();
    Serial.println("RGB OK");

    pinMode(BUZZER, OUTPUT);
    servo_set(0, 180, 180, 180, 180);
    Serial.println("=== READY ===");
    Serial.println("Commands: O/C/A/M/H/P/G/F/R/?");
}

// ========== loop ==========
void loop() {
    wdt_reset();
    if (Serial.available()) handle(Serial.read());
    if (mode == A) auto_update();
    servo_update();

    static uint32_t t_hb = 0;
    if (millis() - t_hb >= 5000) {
        t_hb = millis();
        Serial.print("HB:"); Serial.println(t_hb / 1000);
    }
}
