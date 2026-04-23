#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超声波测距 - HC-SR04
功能：读取超声波传感器距离数据
适用：飞腾派 / 树莓派 / 通用 Linux
"""

import time
import os

# ============== 硬件配置 ==============
# HC-SR04 超声波模块引脚 (BCM 编码)
TRIG_PIN = 23   # 发送引脚
ECHO_PIN = 24   # 接收引脚

# GPIO 操作路径
GPIO_PATH = "/sys/class/gpio"


def gpio_export(pin):
    """导出 GPIO 引脚"""
    export_path = os.path.join(GPIO_PATH, "export")
    try:
        with open(export_path, 'w') as f:
            f.write(str(pin))
        time.sleep(0.1)
    except:
        pass


def gpio_direction(pin, direction):
    """设置 GPIO 方向"""
    pin_path = os.path.join(GPIO_PATH, f"gpio{pin}", "direction")
    try:
        with open(pin_path, 'w') as f:
            f.write(direction)
    except:
        pass


def gpio_write(pin, value):
    """写入 GPIO 值"""
    pin_path = os.path.join(GPIO_PATH, f"gpio{pin}", "value")
    try:
        with open(pin_path, 'w') as f:
            f.write('1' if value else '0')
    except:
        pass


def gpio_read(pin):
    """读取 GPIO 值"""
    pin_path = os.path.join(GPIO_PATH, f"gpio{pin}", "value")
    try:
        with open(pin_path, 'r') as f:
            return int(f.read().strip())
    except:
        return 0


def setup():
    """初始化 GPIO"""
    # 导出引脚
    gpio_export(TRIG_PIN)
    gpio_export(ECHO_PIN)

    # 设置方向
    gpio_direction(TRIG_PIN, 'out')
    gpio_direction(ECHO_PIN, 'in')

    # 初始低电平
    gpio_write(TRIG_PIN, False)

    print("[信息] 等待传感器稳定...")
    time.sleep(2)


def measure_distance():
    """测量距离（厘米）"""
    # 发送触发信号 (至少 10us)
    gpio_write(TRIG_PIN, True)
    time.sleep(0.00001)  # 10微秒
    gpio_write(TRIG_PIN, False)

    # 等待回响开始 (ECHO 变为 HIGH)
    timeout_start = time.time()
    while gpio_read(ECHO_PIN) == 0:
        if time.time() - timeout_start > 0.1:
            return -1
    pulse_start = time.time()

    # 等待回响结束 (ECHO 变为 LOW)
    timeout_start = time.time()
    while gpio_read(ECHO_PIN) == 1:
        if time.time() - timeout_start > 0.1:
            return -1
    pulse_end = time.time()

    # 计算距离
    # 声速 343m/s = 34300cm/s
    # 距离 = 时间差 × 声速 / 2（往返）
    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 34300 / 2

    return round(distance, 2)


def cleanup():
    """清理 GPIO"""
    try:
        # 取消导出
        unexport_path = os.path.join(GPIO_PATH, "unexport")
        with open(unexport_path, 'w') as f:
            f.write(str(TRIG_PIN))
        with open(unexport_path, 'w') as f:
            f.write(str(ECHO_PIN))
    except:
        pass


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
        cleanup()
        print("[信息] GPIO 已清理")


if __name__ == "__main__":
    run()


if __name__ == "__main__":
    run()
