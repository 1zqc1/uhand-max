#include <FastLED.h>
#include <Servo.h>
#include "tone.h"
#include "actions.h"
#include "uhand_servo.h"

// ========== 硬件配置开关 ==========
#define USE_MPU6050 0
#define USE_ULTRASOUND 1

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
// 结构体定义 - 使用结构体+指针优化
// ============================================

// 手指角度目标结构
typedef struct {
  uint8_t thumb;      // 大拇指
  uint8_t index;      // 食指
  uint8_t middle;     // 中指
  uint8_t ring;       // 无名指
  uint8_t pinky;      // 小拇指
} FingerAngles;

// 动作状态枚举
typedef enum {
  GRIP_OPEN = 0,      // 张开
  GRIP_PARTIAL = 1,   // 半开
  GRIP_READY = 2,     // 准备抓取
  GRIP_GRASP = 3,     // 抓取
  GRIP_HOLD = 4,      // 保持
  GRIP_RELEASE = 5    // 释放
} GripState;

// 平滑控制参数结构
typedef struct {
  FingerAngles current;      // 当前角度
  FingerAngles target;       // 目标角度
  FingerAngles delta;        // 每次更新增量
  uint16_t step_interval;    // 步进间隔(ms)
  uint32_t last_update;      // 上次更新时间
} SmoothControl;

// ============================================
// 常量定义
// ============================================

// 距离阈值
#define DIST_MAX 500       // 最远距离(mm) - 张开
#define DIST_MIN 50        // 最近距离(mm) - 握拳
#define DIST_CLOSE 50       // 小于此距离直接握拳

// 手指角度定义
#define THUMB_OPEN   180    // 大拇指张开角度
#define THUMB_CLOSE  0      // 大拇指握拳角度
#define FINGER_OPEN  0      // 手指张开角度
#define FINGER_CLOSE 180    // 手指握拳角度

// 全局变量
static SmoothControl gripper;        // 抓取器控制
static uint16_t current_distance = 500;
static uint16_t filtered_distance = 500;

// 目标角度结构体（用于连续映射）
static FingerAngles target_by_distance;

// 动作组数据定义
uint8_t action[action_count][7] =
    {
      {1, 0,   0,   0,   0,   0,   90},
      {1, 180, 180, 180, 180, 180, 0},
      {1, 19,  43,  40,  8,   23,  116}
    };

// MPU6050 变量（占位）
int ax_offset, ay_offset, az_offset, gx_offset, gy_offset, gz_offset;
float radianX, radianY, radianX_last, radianY_last, radianYaw_last;

/* 引脚定义 */
const static uint8_t servoPins[6] = { 7, 6, 5, 4, 3, 2 };
const static uint8_t buzzerPin = 11;
const static uint8_t rgbPin = 13;
const static uint8_t gimbal_servo_idx = 5;
static uint8_t gimbal_fixed_angle = 90;

// 动作组控制对象
HW_ACTION_CTL action_ctl;
static CRGB rgbs[1];
Servo servos[6];

// 蜂鸣器相关
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

// ============================================
// 抓取器初始化
// ============================================
static void gripper_init(void) {
  // 初始角度 - 张开
  gripper.current.thumb = 180;
  gripper.current.index = 0;
  gripper.current.middle = 0;
  gripper.current.ring = 0;
  gripper.current.pinky = 0;

  // 目标角度相同
  gripper.target = gripper.current;
  gripper.step_interval = 14;  // 灵敏度+5%: 15ms -> 14ms
  gripper.last_update = 0;
}

// ============================================
// 指数滤波
// ============================================
static uint16_t exponential_filter(uint16_t new_val, uint16_t old_val, float alpha) {
  return (uint16_t)((float)new_val * alpha + (float)old_val * (1.0f - alpha));
}

// ============================================
// 计算步进值 (指数缓动) - 灵敏度+5%
// ============================================
static int8_t calculate_step(uint8_t current, uint8_t target, uint8_t max_step) {
  if (current == target) return 0;

  int16_t diff = (int16_t)target - (int16_t)current;
  // 灵敏度+5%: 分3.8步完成（原4步）
  int16_t step = diff / 3.8f;

  if (step > 0) {
    return (int8_t)(step > max_step ? max_step : step);
  } else {
    int8_t abs_step = (int8_t)(-step > max_step ? max_step : -step);
    return -abs_step;
  }
}

// ============================================
// 抓取器更新 (平滑控制)
// ============================================
static void gripper_update(void) {
  uint32_t now = millis();

  // 步进间隔控制
  if (now - gripper.last_update < gripper.step_interval) return;
  gripper.last_update = now;

  // 指数缓动更新每个手指
  int8_t step_thumb = calculate_step(gripper.current.thumb, gripper.target.thumb, 3);
  int8_t step_index = calculate_step(gripper.current.index, gripper.target.index, 3);
  int8_t step_middle = calculate_step(gripper.current.middle, gripper.target.middle, 3);
  int8_t step_ring = calculate_step(gripper.current.ring, gripper.target.ring, 3);
  int8_t step_pinky = calculate_step(gripper.current.pinky, gripper.target.pinky, 3);

  // 更新当前角度
  gripper.current.thumb += step_thumb;
  gripper.current.index += step_index;
  gripper.current.middle += step_middle;
  gripper.current.ring += step_ring;
  gripper.current.pinky += step_pinky;
}

// ============================================
// setup
// ============================================
void setup() {
  Serial.begin(9600);
  Serial.setTimeout(500);

  Serial.println("=== START ===");
  delay(100);

  i2c_init();
  Serial.println("I2C init OK");

  for (int i = 0; i < 6; ++i) {
    servos[i].attach(servoPins[i], 500, 2500);
  }
  Serial.println("Servos OK");

  // 初始化抓取器
  gripper_init();

  // 初始位置 - 张开
  servos[0].write(gripper.current.thumb);
  servos[1].write(gripper.current.index);
  servos[2].write(gripper.current.middle);
  servos[3].write(gripper.current.ring);
  servos[4].write(gripper.current.pinky);
  servos[5].write(90);
  delay(500);

  FastLED.addLeds<WS2812, rgbPin, GRB>(rgbs, 1);
  rgbs[0] = CRGB(0, 100, 0);
  FastLED.show();
  Serial.println("RGB OK");

  pinMode(buzzerPin, OUTPUT);
  digitalWrite(buzzerPin, HIGH);
  delay(100);
  digitalWrite(buzzerPin, LOW);
  Serial.println("Buzzer OK");

#if !USE_MPU6050
  Serial.println("MPU6050 SKIP");
  ax_offset = 0; ay_offset = 0; az_offset = 8192;
  gx_offset = 0; gy_offset = 0; gz_offset = 0;
#endif

#if !USE_ULTRASOUND
  Serial.println("Ultrasound SKIP");
#else
  Serial.println("Ultrasound init...");
  delay(200);
  int test_dist = bbFilter();
  if (test_dist > 0) {
    Serial.print("Ultrasound OK: ");
    Serial.println(test_dist);
  } else {
    Serial.println("Ultrasound FAIL");
  }
#endif

  Serial.println("=== READY ===");
}

// ============================================
// loop
// ============================================
void loop() {
  action_ctl.blue_ctl_receive();
  action_ctl.blue_task();

#if USE_ULTRASOUND
  gripper_task();
#endif

  tune_task();
  servo_control();
  action_ctl.action_task();
}

// ============================================
// 抓取器任务 - 连续映射控制
// ============================================
void gripper_task(void)
{
  static uint32_t last_sensor_tick = 0;

  // 50ms 采样间隔
  if (millis() - last_sensor_tick < 50) return;
  last_sensor_tick = millis();

  // 读取并滤波距离
  int dis = bbFilter();
  if (dis > 0) {
    // 限制范围并滤波
    if (dis < DIST_MIN) dis = DIST_MIN;
    if (dis > DIST_MAX) dis = DIST_MAX;
    filtered_distance = exponential_filter(dis, filtered_distance, 0.3f);
    current_distance = filtered_distance;
  }

  // 连续映射：将距离映射到手指角度
  // 500mm -> 张开, 50mm -> 握拳
  uint16_t dist_range = DIST_MAX - DIST_MIN;
  uint16_t dist_offset = current_distance - DIST_MIN;

  // 使用指数映射，距离越近变化越快
  float ratio = (float)dist_offset / (float)dist_range;
  float grip_ratio = pow(ratio, 0.8f);  // 指数映射，0.8使近距离变化更快

  // 计算目标角度
  uint8_t finger_angle = (uint8_t)(grip_ratio * (FINGER_CLOSE - FINGER_OPEN));  // 0-180
  uint8_t thumb_angle = (uint8_t)(grip_ratio * (THUMB_CLOSE - THUMB_OPEN) + THUMB_OPEN);  // 180-0

  // 设置目标角度
  gripper.target.thumb = thumb_angle;
  gripper.target.index = finger_angle;
  gripper.target.middle = finger_angle;
  gripper.target.ring = finger_angle;
  gripper.target.pinky = finger_angle;

  // 更新抓取器角度
  gripper_update();

  // LED颜色根据距离渐变
  // 绿(远) -> 黄(中) -> 红(近)
  uint8_t r, g, b;
  if (current_distance > 350) {
    // 远：绿色
    r = 0; g = 255; b = 0;
  } else if (current_distance > 150) {
    // 中：黄色渐变
    uint16_t mid = current_distance - 150;
    r = (uint8_t)(255 * mid / 200.0f);
    g = 255;
    b = 0;
  } else {
    // 近：红色渐变
    uint16_t close = 150 - current_distance;
    r = 255;
    g = (uint8_t)(255 * close / 150.0f);
    b = 0;
  }

  rgbs[0].r = r;
  rgbs[0].g = g;
  rgbs[0].b = b;
  FastLED.show();

  // 调试信息
  static uint32_t last_print = 0;
  if (millis() - last_print > 500) {
    last_print = millis();
    Serial.print("Dist: ");
    Serial.print(current_distance);
    Serial.print("mm | Finger: ");
    Serial.print(finger_angle);
    Serial.print(" | Thumb: ");
    Serial.println(thumb_angle);
  }

  // 近距离蜂鸣警报
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
// 舵机控制
// ============================================
void servo_control(void) {
  static uint32_t last_tick = 0;
  if (millis() - last_tick < 20) return;
  last_tick = millis();

  // 控制5个手指舵机 (0-4)
  // 大拇指(0) 方向相反，其他方向相同
  servos[0].write(gripper.current.thumb);           // 大拇指
  servos[1].write(gripper.current.index);           // 食指
  servos[2].write(gripper.current.middle);          // 中指
  servos[3].write(gripper.current.ring);            // 无名指
  servos[4].write(gripper.current.pinky);           // 小拇指

  // 云台保持固定角度
  servos[5].write(gimbal_fixed_angle);
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

// 蜂鸣器鸣响函数
void play_tune(uint16_t *p, uint32_t beat, uint16_t len) {
  tune = p;
  tune_beat = beat;
  tune_num = len;
}