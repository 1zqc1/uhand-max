/*
 * uhand - 机械手控制程序
 * 功能：上电张开 -> 自动测距 -> 50-500mm由远到近逐渐握拳
 */
#include <FastLED.h>
#include <Servo.h>
#include <Wire.h>
#include <avr/wdt.h>

// 引脚定义
const uint8_t SERVO_PINS[6] = {7, 6, 5, 4, 3, 2};  // 拇指、食指、中指、无名指、小指、第6舵机
#define BUZZER   11
#define RGB_LED  13
#define I2C_ADDR 0x77

// 距离参数
#define DIST_MIN 50
#define DIST_MAX 500

// 手指角度定义
// 拇指：0°=张开，180°=闭合
// 四指：0°=闭合，180°=张开（与拇指运动方向相反）
#define THUMB_OPEN   0
#define THUMB_CLOSE  180
#define FINGER_OPEN  180
#define FINGER_CLOSE 0

// 命令模式
enum Mode { CMD_OPEN = 1, CMD_CLOSE, CMD_AUTO, CMD_HANDSHAKE, CMD_PINCH,
            CMD_GRIP, CMD_POINT, CMD_RELAX, CMD_MANUAL, CMD_RELAX_SEQ };

// 全局状态
static enum Mode mode = CMD_OPEN;
static uint16_t distance = 500;
static uint8_t finger_target[5];    // 5个手指的目标角度
static uint8_t finger_current[5];   // 5个手指的当前角度
static uint32_t t_servo = 0, t_sensor = 0;
static uint32_t t_relax = 0;       // 放松模式定时器
static bool relax_open = true;     // 放松模式：张开/闭合切换
static CRGB led;
static Servo servos[6];

// ========== 超声波读取 ==========
static int ultrasonic_read(void) {
    uint32_t t_start = millis();

    Wire.beginTransmission(I2C_ADDR);
    if (Wire.write(0x00) != 1) { Wire.endTransmission(); return -1; }
    if (Wire.endTransmission() != 0) return -1;

    delay(25);  // 等待CS100A测量

    Wire.requestFrom(I2C_ADDR, (uint8_t)2);
    if (Wire.available() < 2) return -1;
    if (millis() - t_start > 100) return -1;

    uint8_t low = Wire.read();
    uint8_t high = Wire.read();
    uint16_t d = ((uint16_t)high << 8) | low;

    if (d < 10 || d > 4000) return -1;
    return d;
}

// ========== 舵机控制 ==========
// 设置5个手指的目标角度 (拇指, 食指, 中指, 无名指, 小指)
static void finger_set(uint8_t t, uint8_t i, uint8_t m, uint8_t r, uint8_t p) {
    finger_target[0] = t;
    finger_target[1] = i;
    finger_target[2] = m;
    finger_target[3] = r;
    finger_target[4] = p;
}

// 平滑更新所有舵机
static void servo_update(void) {
    if (millis() - t_servo < 14) return;
    t_servo = millis();

    for (uint8_t i = 0; i < 5; i++) {
        if (finger_current[i] != finger_target[i]) {
            int16_t diff = finger_target[i] - finger_current[i];
            finger_current[i] += diff / 4;
            servos[i].write(finger_current[i]);
        }
    }
}

// ========== RGB指示灯 ==========
static void rgb_update(uint16_t d) {
    uint8_t r = 0, g = 0;
    if (d > 350) g = 255;
    else if (d > 150) { r = map(d - 150, 0, 200, 0, 255); g = 255; }
    else { r = 255; g = map(150 - d, 0, 150, 0, 255); }
    led.r = r; led.g = g; led.b = 0;
    FastLED.show();
}

// ========== 自动模式 ==========
// 拇指和四指运动方向相反：
// - 拇指: 0°=张开, 180°=闭合
// - 四指: 180°=张开, 0°=闭合
// 距离由远(500mm)到近(50mm)，逐渐握拳
static void auto_mode(void) {
    if (millis() - t_sensor < 50) return;
    t_sensor = millis();

    int d = ultrasonic_read();
    if (d > 0) distance = constrain(d, DIST_MIN, DIST_MAX);

    // ratio: 0=近(50mm), 1=远(500mm)
    float ratio = (float)(distance - DIST_MIN) / (DIST_MAX - DIST_MIN);
    // grip: 0=握拳(近), 1=张开(远)
    float grip = pow(ratio, 0.8f);

    // 拇指: 张开(0°)→闭合(180°)，与四指相反
    uint8_t thumb = (uint8_t)((1.0f - grip) * 180.0f);
    // 四指: 张开(180°)→闭合(0°)，与拇指相反
    uint8_t finger = (uint8_t)(grip * 180.0f);

    finger_set(thumb, finger, finger, finger, finger);
    rgb_update(distance);

    // 近距离警报
    if (distance < 80) {
        static uint32_t last_beep = 0;
        if (millis() - last_beep > 300) {
            last_beep = millis();
            tone(BUZZER, 1000);
            delay(30);
            noTone(BUZZER);
        }
    }
}

// ========== 命令处理 ==========
static void handle_cmd(char cmd) {
    Serial.print("CMD:");
    switch (cmd) {
        case 'O':  // 张开
            mode = CMD_OPEN;
            finger_set(THUMB_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN);
            Serial.println("OPEN");
            break;
        case 'C':  // 闭合
            mode = CMD_CLOSE;
            finger_set(THUMB_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE);
            Serial.println("CLOSE");
            break;
        case 'A':  // 自动模式
            mode = CMD_AUTO;
            Serial.println("AUTO");
            break;
        case 'M':  // 手动模式（张开状态）
            mode = CMD_OPEN;
            finger_set(THUMB_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN);
            Serial.println("MANUAL");
            break;
        case 'H':  // 握手
            mode = CMD_HANDSHAKE;
            finger_set(90, 120, 150, 160, 170);
            Serial.println("HANDSHAKE");
            break;
        case 'P':  // 捏取
            mode = CMD_PINCH;
            finger_set(30, 30, 180, 180, 180);
            Serial.println("PINCH");
            break;
        case 'G':  // 全握
            mode = CMD_GRIP;
            finger_set(THUMB_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE);
            Serial.println("GRIP");
            break;
        case 'F':  // 指向
            mode = CMD_POINT;
            finger_set(120, 180, 60, 60, 60);
            Serial.println("POINT");
            break;
        case 'R':  // 放松 - 有节奏地抓取
            mode = CMD_RELAX_SEQ;
            relax_open = true;
            t_relax = millis();
            finger_set(THUMB_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN);
            Serial.println("RELAX");
            break;
        case '?':  // 查询
            Serial.println("QUERY");
            Serial.print("DIST:"); Serial.println(distance);
            return;
        default:
            Serial.println("UNKNOWN");
            return;
    }
    Serial.print("MODE:"); Serial.println(mode);
}

// ========== 初始化 ==========
void setup() {
    wdt_enable(WDTO_8S);
    Serial.begin(9600);
    Serial.println("=== START ===");

    // 初始化6个舵机
    for (uint8_t i = 0; i < 6; i++) {
        servos[i].attach(SERVO_PINS[i], 500, 2500);
    }
    Serial.println("Servos OK");

    // RGB LED
    FastLED.addLeds<WS2812, RGB_LED, GRB>(&led, 1);
    led = CRGB(0, 100, 0);
    FastLED.show();
    Serial.println("RGB OK");

    pinMode(BUZZER, OUTPUT);
    Wire.begin();

    // 上电：张开状态
    finger_set(THUMB_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN);
    for (uint8_t i = 0; i < 5; i++) finger_current[i] = THUMB_OPEN;

    Serial.println("=== READY ===");
    Serial.println("Commands: O/C/A/M/H/P/G/F/R/?");
}

// ========== 主循环 ==========
void loop() {
    wdt_reset();

    if (Serial.available()) handle_cmd(Serial.read());

    if (mode == CMD_AUTO) auto_mode();

    // 放松模式：每800ms切换张开/闭合
    if (mode == CMD_RELAX_SEQ) {
        if (millis() - t_relax >= 800) {
            t_relax = millis();
            relax_open = !relax_open;
            if (relax_open) {
                finger_set(THUMB_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN);
            } else {
                finger_set(THUMB_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE);
            }
        }
    }

    servo_update();

    // 心跳
    static uint32_t t_hb = 0;
    if (millis() - t_hb >= 5000) {
        t_hb = millis();
        Serial.print("HB:"); Serial.println(t_hb / 1000);
    }
}
