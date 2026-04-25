/*
 * uhand - 机械手控制程序
 * 功能：上电张开 -> 自动模式 -> 超声波控制抓取 + MPU6050控制云台
 */
#include <FastLED.h>
#include <Servo.h>
#include <Wire.h>
#include <avr/wdt.h>

// ================= 引脚定义 =================
const uint8_t SERVO_PINS[6] = {7, 6, 5, 4, 3, 2};  // 拇指、食指、中指、无名指、小指、云台
#define BUZZER    11
#define RGB_LED   13
#define I2C_ADDR_ULTRA  0x77  // 超声波传感器地址
#define I2C_ADDR_MPU   0x68   // MPU6050地址

// ================= 距离参数 =================
#define DIST_MIN 50
#define DIST_MAX 500

// ================= 手指角度定义 =================
#define THUMB_OPEN   0
#define THUMB_CLOSE  180
#define FINGER_OPEN  180
#define FINGER_CLOSE 0

// ================= 命令模式 =================
enum Mode { CMD_OPEN = 1, CMD_CLOSE, CMD_AUTO, CMD_HANDSHAKE, CMD_PINCH,
            CMD_GRIP, CMD_POINT, CMD_RELAX, CMD_MANUAL, CMD_RELAX_SEQ };

// ================= 全局状态 =================
static enum Mode mode = CMD_OPEN;
static uint16_t distance = 500;

// 手指控制
static uint8_t finger_target[5];
static uint8_t finger_current[5];
static uint32_t t_servo = 0, t_sensor = 0;

// 放松模式
static uint32_t t_relax = 0;
static bool relax_open = true;

// MPU6050云台控制
static float gimbal_pos = 90;      // 云台目标角度
static float angleY = 0;          // Y轴倾斜角（左右翻转）
static int16_t ax_raw, ay_raw, az_raw, gx_raw, gy_raw, gz_raw;

// PID参数（防抖优化）
#define PID_KP  1.5    // 比例系数
#define PID_KI  0.0    // 积分系数（已改用带衰减的积分）
#define PID_KD  0.3    // 微分系数（已降低）
static float pid_integral = 0;     // 积分累积

static CRGB led;
static Servo servos[6];

// ================= 超声波读取 =================
static int ultrasonic_read(void) {
    Wire.beginTransmission(I2C_ADDR_ULTRA);
    if (Wire.write(0x00) != 1) { Wire.endTransmission(); return -1; }
    if (Wire.endTransmission() != 0) return -1;

    delay(25);  // 等待CS100A测量

    Wire.requestFrom(I2C_ADDR_ULTRA, (uint8_t)2);
    if (Wire.available() < 2) return -1;

    uint8_t low = Wire.read();
    uint8_t high = Wire.read();
    uint16_t d = ((uint16_t)high << 8) | low;

    if (d < 10 || d > 4000) return -1;
    return d;
}

// ================= MPU6050读取 =================
static void mpu_read(void) {
    Wire.beginTransmission(I2C_ADDR_MPU);
    Wire.write(0x3B);  // 加速度计数据首地址
    Wire.endTransmission(false);
    Wire.requestFrom(I2C_ADDR_MPU, (uint8_t)14);

    if (Wire.available() >= 14) {
        ax_raw = (Wire.read() << 8) | Wire.read();
        ay_raw = (Wire.read() << 8) | Wire.read();
        az_raw = (Wire.read() << 8) | Wire.read();
        // 温度跳过
        Wire.read(); Wire.read();
        gx_raw = (Wire.read() << 8) | Wire.read();
        gy_raw = (Wire.read() << 8) | Wire.read();
        gz_raw = (Wire.read() << 8) | Wire.read();
    }
}

// ================= MPU6050更新（Y轴倾斜+二阶低通滤波） =================
static void mpu_update(void) {
    static uint32_t t = 0;
    if (millis() - t < 20) return;  // 降低采样频率到50Hz
    t = millis();

    mpu_read();

    // 二阶低通滤波（更平滑）
    static float ax_f1 = 0, az_f1 = 0, ax_f2 = 0, az_f2 = 0;
    ax_f1 = ax_f1 * 0.5 + ax_raw * 0.5;
    az_f1 = az_f1 * 0.5 + az_raw * 0.5;
    ax_f2 = ax_f2 * 0.7 + ax_f1 * 0.3;
    az_f2 = az_f2 * 0.7 + az_f1 * 0.3;

    // 重力补偿：计算Y轴倾斜角
    angleY = atan2(ax_f2, az_f2) * 57.3f;
}

// ================= 云台PID控制（防抖版） =================
static void gimbal_control(void) {
    // 目标角度 = 90 + Y轴倾斜角
    float target = 90.0f + angleY;
    target = constrain(target, 30.0f, 150.0f);

    float error = target - gimbal_pos;

    // 积分项带衰减，防止累积过冲
    pid_integral = pid_integral * 0.85 + error * 0.1;
    pid_integral = constrain(pid_integral, -20.0f, 20.0f);

    // 微分项滤波
    static float last_error = 0, d_filtered = 0;
    float derivative = error - last_error;
    d_filtered = d_filtered * 0.6 + derivative * 0.4;
    last_error = error;

    // PID输出
    float output = PID_KP * error + pid_integral + PID_KD * d_filtered;

    gimbal_pos += output;
    gimbal_pos = constrain(gimbal_pos, 30.0f, 150.0f);

    servos[5].write((uint8_t)gimbal_pos);
}

// ================= 手指控制 =================
static void finger_set(uint8_t t, uint8_t i, uint8_t m, uint8_t r, uint8_t p) {
    finger_target[0] = t;
    finger_target[1] = i;
    finger_target[2] = m;
    finger_target[3] = r;
    finger_target[4] = p;
}

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

// ================= RGB指示灯 =================
static void rgb_update(uint16_t d) {
    uint8_t r = 0, g = 0;
    if (d > 350) g = 255;
    else if (d > 150) { r = map(d - 150, 0, 200, 0, 255); g = 255; }
    else { r = 255; g = map(150 - d, 0, 150, 0, 255); }
    led.r = r; led.g = g; led.b = 0;
    FastLED.show();
}

static void gimbal_led(float angle) {
    if (angle > 10) led = CRGB::Blue;
    else if (angle < -10) led = CRGB::Red;
    else led = CRGB::Green;
    FastLED.show();
}

// ================= 自动模式 =================
static void auto_mode(void) {
    if (millis() - t_sensor < 50) return;
    t_sensor = millis();

    int d = ultrasonic_read();
    if (d > 0) distance = constrain(d, DIST_MIN, DIST_MAX);

    // 超声波控制手指
    // ratio: 0=最近(50mm), 1=最远(500mm)
    // 远距离张开，近距离闭合
    float ratio = (float)(distance - DIST_MIN) / (DIST_MAX - DIST_MIN);
    float grip = pow(ratio, 0.8f);

    uint8_t thumb = (uint8_t)((1.0f - grip) * 180.0f);
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

// ================= 命令处理 =================
static void handle_cmd(char cmd) {
    Serial.print("CMD:");
    switch (cmd) {
        case 'O':
            mode = CMD_OPEN;
            finger_set(THUMB_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN);
            Serial.println("OPEN");
            break;
        case 'C':
            mode = CMD_CLOSE;
            finger_set(THUMB_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE);
            Serial.println("CLOSE");
            break;
        case 'A':
            mode = CMD_AUTO;
            Serial.println("AUTO");
            break;
        case 'M':
            mode = CMD_OPEN;
            finger_set(THUMB_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN);
            Serial.println("MANUAL");
            break;
        case 'H':
            mode = CMD_HANDSHAKE;
            finger_set(90, 120, 150, 160, 170);
            Serial.println("HANDSHAKE");
            break;
        case 'P':
            mode = CMD_PINCH;
            finger_set(30, 30, 180, 180, 180);
            Serial.println("PINCH");
            break;
        case 'G':
            mode = CMD_GRIP;
            finger_set(THUMB_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE, FINGER_CLOSE);
            Serial.println("GRIP");
            break;
        case 'F':
            mode = CMD_POINT;
            finger_set(120, 180, 60, 60, 60);
            Serial.println("POINT");
            break;
        case 'R':
            mode = CMD_RELAX_SEQ;
            relax_open = true;
            t_relax = millis();
            finger_set(THUMB_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN);
            Serial.println("RELAX");
            break;
        case '?':
            Serial.println("QUERY");
            Serial.print("DIST:"); Serial.println(distance);
            Serial.print("ANGLE:"); Serial.println((int)angleY);
            return;
        default:
            Serial.println("UNKNOWN");
            return;
    }
    Serial.print("MODE:"); Serial.println(mode);
}

// ================= 初始化 =================
void setup() {
    wdt_enable(WDTO_8S);
    Serial.begin(9600);
    Serial.println("=== START ===");

    // 初始化舵机
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

    // 初始化MPU6050
    Wire.beginTransmission(I2C_ADDR_MPU);
    Wire.write(0x6B);  // PWR_MGMT_1
    Wire.write(0x00);  // 唤醒MPU6050
    if (Wire.endTransmission() == 0) {
        Serial.println("MPU6050 OK");
    } else {
        Serial.println("MPU6050 FAIL");
    }

    // 上电：张开状态
    finger_set(THUMB_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN, FINGER_OPEN);
    for (uint8_t i = 0; i < 5; i++) finger_current[i] = THUMB_OPEN;
    servos[5].write(90);

    Serial.println("=== READY ===");
    Serial.println("Commands: O/C/A/M/H/P/G/F/R/?");
}

// ================= 主循环 =================
void loop() {
    wdt_reset();

    if (Serial.available()) handle_cmd(Serial.read());

    // 自动模式：超声波控制手指
    if (mode == CMD_AUTO) {
        auto_mode();
    }

    // MPU6050和云台控制在所有模式下都运行
    mpu_update();
    gimbal_control();
    gimbal_led(angleY);

    // 放松模式
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
