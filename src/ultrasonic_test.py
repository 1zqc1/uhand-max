#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超声波测距 - CS100A (I2C 接口)
功能：读取超声波传感器距离数据
适用：飞腾派 / 树莓派 / 通用 Linux
"""

import time

# ============== 硬件配置 ==============
# I2C 配置
I2C_BUS = 1           # I2C 总线号 (一般 1)
I2C_ADDR = 0x77       # CS100A I2C 地址

# 寄存器地址
REG_DISTANCE = 0x00    # 距离寄存器


def i2c_read_word(bus, addr, reg):
    """I2C 读取字（16位）"""
    try:
        # 写入寄存器地址
        bus.write_byte(addr, reg)
        time.sleep(0.01)

        # 读取两个字节
        low = bus.read_byte(addr)
        high = bus.read_byte(addr)

        # 合成 16 位数据
        value = (high << 8) | low
        return value
    except Exception as e:
        print(f"[错误] I2C 读取失败: {e}")
        return -1


def setup_i2c():
    """检查并初始化 I2C"""
    try:
        import smbus
        bus = smbus.SMBus(I2C_BUS)
        print(f"[成功] I2C 总线 {I2C_BUS} 已打开")

        # 检测设备
        try:
            bus.read_byte(I2C_ADDR)
            print(f"[成功] 找到设备 0x{I2C_ADDR:02X}")
        except:
            print(f"[警告] 未找到设备 0x{I2C_ADDR:02X}")

        return bus
    except Exception as e:
        print(f"[错误] I2C 初始化失败: {e}")
        return None


def measure_distance(bus):
    """测量距离（毫米）"""
    if bus is None:
        return -1

    try:
        # CS100A 读取距离
        # 发送触发命令
        bus.write_byte(I2C_ADDR, 0x01)
        time.sleep(0.1)

        # 读取距离数据
        low = bus.read_byte(I2C_ADDR)
        high = bus.read_byte(I2C_ADDR)

        # 有些模块返回的是 cm，需要确认你的模块手册
        distance_mm = (high << 8) | low

        if distance_mm == 0 or distance_mm > 4000:
            return -1

        return distance_mm

    except Exception as e:
        # 如果上面的方式不行，试试这个
        try:
            bus.write_byte_data(I2C_ADDR, 0x00, 0x01)
            time.sleep(0.1)
            data = bus.read_i2c_block_data(I2C_ADDR, 0x00, 2)
            distance_mm = (data[1] << 8) | data[0]
            return distance_mm
        except:
            return -1


def run():
    """主循环"""
    print("=" * 40)
    print("CS100A 超声波测距 (I2C)")
    print("按 Ctrl+C 退出")
    print("=" * 40)

    bus = setup_i2c()
    if bus is None:
        print("[错误] I2C 初始化失败，退出")
        return

    print("[信息] 开始测距...")

    try:
        while True:
            dist = measure_distance(bus)

            if dist > 0:
                # 转换为厘米显示
                dist_cm = dist / 10.0
                print(f"距离: {dist_cm:.1f} cm", end='')

                if dist < 80:
                    print(" [近]", end='')
                elif dist > 150:
                    print(" [远]", end='')
                else:
                    print(" [中]", end='')
                print()
            else:
                print("距离: 超时或无效")
                print("  (请检查接线是否正确，I2C地址是否正确)")

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[信息] 退出程序")
    finally:
        if bus:
            bus.close()
        print("[信息] 已关闭")


if __name__ == "__main__":
    run()


if __name__ == "__main__":
    run()
