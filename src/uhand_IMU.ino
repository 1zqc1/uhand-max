#include <FastLED.h>
#include <Servo.h>
#include <SoftwareSerial.h>
#include "tone.h"
#include "uhand_servo.h"

// ========== 硬件配置开关 ==========
#define USE_MPU6050 0
#define USE_ULTRASOUND 1

// ========== 软串口定义 (连接USB转TTL) ==========
#define SOFT_RX 10
#define SOFT_TX 12
SoftwareSerial softSerial(SOFT_RX, SOFT_TX);

// ========== BitBang I2C 定义 ==========
#define I2C_SDA 18
#define I2C_SCL 19
#define I2C_ADDR 0x77

// I2C初始化
static void i2c_init(void) {
  pinMode(I2C_SDA, INPUT_PULLUP);
  pinMode(I2C_SCL, INPUT_PULLUP);
}

static void i2c_start(void) {
  pinMode(I2C_SDA, OUTPUT); digitalWrite(I2C_SDA, LOW);
  pinMode(I2C_SCL, OUTPUT); digitalWrite(I2C_SCL, LOW);
  delayMicroseconds(10);
}

static void i2c_stop(void) {
  pinMode(I2C_SDA, OUTPUT); digitalWrite(I2C_SDA, LOW);
  delayMicroseconds(5);
  pinMode(I2C_SCL, INPUT_PULLUP);
  delayMicroseconds(5);
  pinMode(I2C_SDA, INPUT_PULLUP);
  delayMicroseconds(10);
}

static bool i2c_write(uint8_t byte) {
  for (int i = 7; i >= 0; i--) {
    pinMode(I2C_SDA, OUTPUT);
    digitalWrite(I2C_SDA, (byte >> i) & 1 ? HIGH : LOW);
    delayMicroseconds(5);
    pinMode(I2C_SCL, INPUT_PULLUP);
    unsigned long start = micros();
    while (digitalRead(I2C_SCL) == LOW) {
      if ((micros() - start) > 2000) break;
    }
    delayMicroseconds(5);
    pinMode(I2C_SCL, OUTPUT); digitalWrite(I2C_SCL, LOW);
    delayMicroseconds(5);
  }
  pinMode(I2C_SDA, INPUT_PULLUP);
  pinMode(I2C_SCL, INPUT_PULLUP);
  unsigned long start = micros();
  while (digitalRead(I2C_SCL) == LOW) {
    if ((micros() - start) > 2000) break;
  }
  delayMicroseconds(5);
  bool ack = digitalRead(I2C_SDA) == LOW;
  pinMode(I2C_SCL, OUTPUT); digitalWrite(I2C_SCL, LOW);
  delayMicroseconds(10);
  return ack;
}

static uint8_t i2c_read(bool ack) {
  uint8_t byte = 0;
  for (int i = 7; i >= 0; i--) {
    pinMode(I2C_SDA, INPUT_PULLUP);
    pinMode(I2C_SCL, INPUT_PULLUP);
    unsigned long start = micros();
    while (digitalRead(I2C_SCL) == LOW) {
      if ((micros() - start) > 2000) break;
    }
    delayMicroseconds(5);
    if (digitalRead(I2C_SDA)) byte |= (1 << i);
    pinMode(I2C_SCL, OUTPUT); digitalWrite(I2C_SCL, LOW);
    delayMicroseconds(10);
  }
  pinMode(I2C_SDA, OUTPUT);
  digitalWrite(I2C_SDA, ack ? LOW : HIGH);
  delayMicroseconds(5);
  pinMode(I2C_SCL, INPUT_PULLUP);
  unsigned long start = micros();
  while (digitalRead(I2C_SCL) == LOW) {
    if ((micros() - start) > 2000) break;
  }
  delayMicroseconds(5);
  pinMode(I2C_SCL, OUTPUT); digitalWrite(I2C_SCL, LOW);
  delayMicroseconds(10);
  pinMode(I2C_SDA, INPUT_PULLUP);
  return byte;
}

// BitBang 超声波读取
static int bbFilter(void) {
  uint8_t b1 = 0, b2 = 0;
  i2c_start();
  if (!i2c_write(I2C_ADDR << 1)) { i2c_stop(); return -1; }
  i2c_write(0x00);
  i2c_stop();
  delayMicroseconds(15000);
  i2c_start();
  if (!i2c_write((I2C_ADDR << 1) | 1)) { i2c_stop(); return -1; }
  b1 = i2c_read(true);
  b2 = i2c_read(false);
  i2c_stop();
  uint16_t d_big = (b2 << 8) | b1;
  if (d_big >= 10 && d_big <= 4000) return (int)d_big;
  return -1;
}

// ============================================
// 常量定义
// ============================================

#define DIST_MAX 500
#define DIST_MIN 50

// 张开状态：手指180度，大拇指0度
#define FINGER_OPEN  180
#define THUMB_OPEN   0

// 闭合状态：手指0度，大拇指180度
#define FINGER_CLOSE 0
#define THUMB_CLOSE  180

// 串口命令
#define CMD_OPEN   1
#define CMD_CLOSE  2
#define CMD_AUTO   3

// ============================================
// 全局变量
// ============================================

SmoothControl gripper;
static uint16_t current_distance = 500;
static uint16_t filtered_distance = 500;
static uint8_t control_mode = CMD_AUTO;

const static uint8_t servoPins[6] = { 7, 6, 5, 4, 3, 2 };
const static uint8_t buzzerPin = 11;
const static uint8_t rgbPin = 13;
static uint8_t gimbal_fixed_angle = 90;

static CRGB rgbs[1];
Servo servos[6];

static uint16_t tune_num = 0;
static uint32_t tune_beat = 10;
static uint16_t *tune;

// ============================================
// 函数声明
// ============================================
static void gripper_init(void);
static void gripper_update(void);
static int8_t calculate_step(uint8_t current, uint8_t target, uint8_t max_step);
static uint16_t exponential_filter(uint16_t new_val, uint16_t old_val, float alpha);
static void gripper_set_target(uint8_t thumb, uint8_t fingers);
static void serial_task(void);
static void write_all_servos(void);

// ============================================
// 抓取器初始化 - 张开状态
// ============================================
static void gripper_init(void) {
  gripper.current.thumb = THUMB_OPEN;
  gripper.current.index = FINGER_OPEN;
  gripper.current.middle = FINGER_OPEN;
  gripper.current.ring = FINGER_OPEN;
  gripper.current.pinky = FINGER_OPEN;

  gripper.target.thumb = THUMB_OPEN;
  gripper.target.index = FINGER_OPEN;
  gripper.target.middle = FINGER_OPEN;
  gripper.target.ring = FINGER_OPEN;
  gripper.target.pinky = FINGER_OPEN;

  gripper.step_interval = 14;
  gripper.last_update = 0;
}

// ============================================
// 指数滤波
// ============================================
static uint16_t exponential_filter(uint16_t new_val, uint16_t old_val, float alpha) {
  return (uint16_t)((float)new_val * alpha + (float)old_val * (1.0f - alpha));
}

// ============================================
// 计算步进值
// ============================================
static int8_t calculate_step(uint8_t current, uint8_t target, uint8_t max_step) {
  if (current == target) return 0;

  int16_t diff = (int16_t)target - (int16_t)current;

  if (diff > 0) {
    int16_t step = diff / 3.8f;
    return (int8_t)(step > max_step ? max_step : step);
  } else {
    int16_t step = -diff / 3.8f;
    int8_t abs_step = (int8_t)(step > max_step ? max_step : step);
    return -abs_step;
  }
}

// ============================================
// 设置抓取器目标角度
// ============================================
static void gripper_set_target(uint8_t thumb, uint8_t fingers) {
  gripper.target.thumb = thumb;
  gripper.target.index = fingers;
  gripper.target.middle = fingers;
  gripper.target.ring = fingers;
  gripper.target.pinky = fingers;
}

// ============================================
// 抓取器更新
// ============================================
static void gripper_update(void) {
  uint32_t now = millis();

  if (now - gripper.last_update < gripper.step_interval) return;
  gripper.last_update = now;

  int8_t step_thumb = calculate_step(gripper.current.thumb, gripper.target.thumb, 5);
  int8_t step_index = calculate_step(gripper.current.index, gripper.target.index, 5);
  int8_t step_middle = calculate_step(gripper.current.middle, gripper.target.middle, 5);
  int8_t step_ring = calculate_step(gripper.current.ring, gripper.target.ring, 5);
  int8_t step_pinky = calculate_step(gripper.current.pinky, gripper.target.pinky, 5);

  gripper.current.thumb += step_thumb;
  gripper.current.index += step_index;
  gripper.current.middle += step_middle;
  gripper.current.ring += step_ring;
  gripper.current.pinky += step_pinky;
}

// ============================================
// 写入所有舵机
// ============================================
static void write_all_servos(void) {
  servos[0].write(gripper.current.thumb);
  servos[1].write(gripper.current.index);
  servos[2].write(gripper.current.middle);
  servos[3].write(gripper.current.ring);
  servos[4].write(gripper.current.pinky);
  servos[5].write(gimbal_fixed_angle);
}

// ============================================
// 串口命令处理
// ============================================
static void serial_task(void) {
  if (softSerial.available() > 0) {
    char cmd = softSerial.read();

    switch (cmd) {
      case 'O':
        control_mode = CMD_OPEN;
        gripper_set_target(THUMB_OPEN, FINGER_OPEN);
        softSerial.println("CMD:OPEN");
        break;

      case 'C':
        control_mode = CMD_CLOSE;
        gripper_set_target(THUMB_CLOSE, FINGER_CLOSE);
        softSerial.println("CMD:CLOSE");
        break;

      case 'A':
        control_mode = CMD_AUTO;
        softSerial.println("CMD:AUTO");
        break;

      case 'M':
        control_mode = CMD_OPEN;
        gripper_set_target(THUMB_OPEN, FINGER_OPEN);
        softSerial.println("CMD:MANUAL");
        break;

      case '?':
        softSerial.print("DIST:");
        softSerial.println(current_distance);
        softSerial.print("MODE:");
        softSerial.println(control_mode);
        break;
    }
  }
}

// ============================================
// setup
// ============================================
void setup() {
  // 初始化软串口（用于与下位机通信）
  // RX=D10, TX=D12
  softSerial.begin(9600);

  softSerial.println("=== START ===");
  delay(200);

  i2c_init();
  softSerial.println("I2C init OK");

  for (int i = 0; i < 6; ++i) {
    servos[i].attach(servoPins[i], 500, 2500);
  }
  softSerial.println("Servos OK");

  gripper_init();
  softSerial.println("Gripper init OK");

  write_all_servos();
  softSerial.println("Servos written - OPEN");

  delay(500);

  FastLED.addLeds<WS2812, rgbPin, GRB>(rgbs, 1);
  rgbs[0] = CRGB(0, 100, 0);
  FastLED.show();
  softSerial.println("RGB OK");

  pinMode(buzzerPin, OUTPUT);
  digitalWrite(buzzerPin, HIGH);
  delay(100);
  digitalWrite(buzzerPin, LOW);
  softSerial.println("Buzzer OK");

#if !USE_MPU6050
  softSerial.println("MPU6050 SKIP");
#endif

#if !USE_ULTRASOUND
  softSerial.println("Ultrasound SKIP");
#else
  softSerial.println("Ultrasound init...");
  delay(200);
  int test_dist = bbFilter();
  if (test_dist > 0) {
    softSerial.print("Ultrasound OK: ");
    softSerial.println(test_dist);
  } else {
    softSerial.println("Ultrasound FAIL");
  }
#endif

  softSerial.println("=== READY ===");
  softSerial.println("Commands: O=Open, C=Close, A=Auto, M=Manual, ?=Status");

  gripper_set_target(THUMB_OPEN, FINGER_OPEN);
  write_all_servos();
}

// ============================================
// loop
// ============================================
void loop() {
  serial_task();

#if USE_ULTRASOUND
  if (control_mode == CMD_AUTO) {
    gripper_task();
  }
#endif

  gripper_update();
  write_all_servos();

  tune_task();
}

// ============================================
// 抓取器任务（自动模式）
// ============================================
void gripper_task(void) {
  static uint32_t last_sensor_tick = 0;

  if (millis() - last_sensor_tick < 50) return;
  last_sensor_tick = millis();

  int dis = bbFilter();
  if (dis > 0) {
    if (dis < DIST_MIN) dis = DIST_MIN;
    if (dis > DIST_MAX) dis = DIST_MAX;
    filtered_distance = exponential_filter(dis, filtered_distance, 0.3f);
    current_distance = filtered_distance;
  }

  uint16_t dist_range = DIST_MAX - DIST_MIN;
  uint16_t dist_offset = current_distance - DIST_MIN;

  float ratio = (float)dist_offset / (float)dist_range;
  float grip_ratio = 1.0f - pow(ratio, 0.8f);

  uint8_t finger_angle = (uint8_t)((1.0f - grip_ratio) * FINGER_OPEN);
  uint8_t thumb_angle = (uint8_t)(grip_ratio * THUMB_CLOSE);

  gripper_set_target(thumb_angle, finger_angle);

  uint8_t r, g, b;
  if (current_distance > 350) {
    r = 0; g = 255; b = 0;
  } else if (current_distance > 150) {
    uint16_t mid = current_distance - 150;
    r = (uint8_t)(255 * mid / 200.0f);
    g = 255;
    b = 0;
  } else {
    uint16_t close = 150 - current_distance;
    r = 255;
    g = (uint8_t)(255 * close / 150.0f);
    b = 0;
  }

  rgbs[0].r = r;
  rgbs[0].g = g;
  rgbs[0].b = b;
  FastLED.show();

  if (current_distance < 80) {
    static uint32_t last_beep = 0;
    if (millis() - last_beep > 300) {
      last_beep = millis();
      tone(buzzerPin, 1000);
      delay(30);
      noTone(buzzerPin);
    }
  }
}

// ============================================
// 蜂鸣器任务
// ============================================
void tune_task(void) {
  static uint32_t l_tune_beat = 0;
  static uint32_t last_tick = 0;
  if (millis() - last_tick < l_tune_beat && tune_beat == l_tune_beat) return;
  l_tune_beat = tune_beat;
  last_tick = millis();
  if (tune_num > 0) {
    tune_num -= 1;
    tone(buzzerPin, *tune++);
  } else {
    noTone(buzzerPin);
    tune_beat = 10;
    l_tune_beat = 10;
  }
}

void play_tune(uint16_t *p, uint32_t beat, uint16_t len) {
  tune = p;
  tune_beat = beat;
  tune_num = len;
}