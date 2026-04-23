#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超声波测距 - HC-SR04
功能：读取超声波传感器距离数据
"""

import RPi.GPIO as GPIO
import time

# ============== 硬件配置 ==============
# HC-SR04 超声波模块引脚
TRIG_PIN = 23   # 发送引脚
ECHO_PIN = 24   # 接收引脚


def setup():
    """初始化 GPIO"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TRIG_PIN, GPIO.OUT)
    GPIO.setup(ECHO_PIN, GPIO.IN)
    GPIO.output(TRIG_PIN, False)
    print("[信息] 等待传感器稳定...")
    time.sleep(2)  # 等待传感器稳定


def measure_distance():
    """测量距离（厘米）"""
    # 发送触发信号
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)  # 10微秒触发信号
    GPIO.output(TRIG_PIN, False)

    # 等待回响开始
    pulse_start = time.time()
    timeout_start = pulse_start

    while GPIO.input(ECHO_PIN) == 0:
        pulse_start = time.time()
        if pulse_start - timeout_start > 0.1:  # 超时100ms
            return -1

    # 等待回响结束
    pulse_end = time.time()
    timeout_start = pulse_end

    while GPIO.input(ECHO_PIN) == 1:
        pulse_end = time.time()
        if pulse_end - timeout_start > 0.1:  # 超时100ms
            return -1

    # 计算距离
    # 声速 343m/s = 34300cm/s
    # 距离 = 时间差 × 声速 / 2（往返）
    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 34300 / 2

    return round(distance, 2)


def run():
    """主循环"""
    setup()
    print("=" * 40)
    print("超声波测距测试")
    print("按 Ctrl+C 退出")
    print("=" * 40)

    try:
        while True:
            dist = measure_distance()
            if dist > 0:
                print(f"距离: {dist:.2f} cm", end='')
                if dist < 10:
                    print(" [近]", end='')
                elif dist > 100:
                    print(" [远]", end='')
                else:
                    print(" [中]", end='')
                print()
            else:
                print("距离: 超时")
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[信息] 退出程序")
    finally:
        GPIO.cleanup()
        print("[信息] GPIO 已清理")


if __name__ == "__main__":
    run()
