#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CS100A 超声波测距 - I2C 初始化 + 扫描 + 测距
适用：飞腾派 V3.0 (CEK8903)
"""

import time
import os
import subprocess

# ============== I2C 配置 ==============
I2C_BUS = 1           # I2C1 总线
CS100A_ADDR = 0x77    # CS100A I2C 地址


def run_cmd(cmd):
    """执行系统命令"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def enable_i2c():
    """启用 I2C"""
    print("[信息] 检查 I2C 状态...")

    # 检查 /dev/i2c-1 是否存在
    if os.path.exists('/dev/i2c-1'):
        print("[成功] I2C-1 已存在")
        return True

    # 尝试加载 i2c-dev 模块
    print("[信息] 加载 i2c-dev 模块...")
    run_cmd("modprobe i2c-dev")

    # 检查 again
    if os.path.exists('/dev/i2c-1'):
        print("[成功] I2C-1 已就绪")
        return True

    # 尝试通过设备树启用 (飞腾派)
    print("[信息] 尝试启用 I2C1...")
    run_cmd("echo 1 > /sys/class/i2c-dev/i2c-1/device/new_device 2>/dev/null")
    run_cmd("echo cs100a 0x77 > /sys/class/i2c-dev/i2c-1/device/new_device 2>/dev/null")

    time.sleep(0.5)

    if os.path.exists('/dev/i2c-1'):
        print("[成功] I2C-1 已就绪")
        return True

    print("[警告] I2C-1 未找到，尝试使用 I2C-0...")
    if os.path.exists('/dev/i2c-0'):
        print("[成功] 使用 I2C-0")
        return True

    return False


def scan_i2c_devices(bus_num=1):
    """扫描 I2C 总线上的所有设备"""
    print(f"\n{'='*50}")
    print(f"扫描 I2C-{bus_num} 总线上的设备...")
    print(f"{'='*50}")

    device_path = f"/dev/i2c-{bus_num}"
    if not os.path.exists(device_path):
        print(f"[错误] {device_path} 不存在")
        return []

    # 方法1: 使用 i2cdetect 命令
    ret, out, err = run_cmd(f"i2cdetect -y {bus_num} 2>/dev/null")
    if ret == 0 and out:
        print(out)
        # 解析输出获取地址
        addrs = []
        for line in out.split('\n')[1:]:
            if ':' in line:
                parts = line.split(':')[1].split()
                for p in parts:
                    if p not in ['--', 'UU']:
                        try:
                            addrs.append(int(p, 16))
                        except:
                            pass
        return addrs

    # 方法2: 使用 Python smbus 扫描
    try:
        import smbus
        bus = smbus.SMBus(bus_num)
        found = []

        print(f"     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f")
        for i in range(16):
            line = f"{i:02x}: "
            for j in range(16):
                addr = i * 16 + j
                try:
                    bus.read_byte(addr)
                    line += f"{addr:02x} "
                    found.append(addr)
                except:
                    line += "-- "
            print(line)

        print(f"\n找到 {len(found)} 个设备: {[hex(a) for a in found]}")
        bus.close()
        return found

    except Exception as e:
        print(f"[错误] 扫描失败: {e}")
        return []


def read_distance(bus):
    """读取 CS100A 距离"""
    try:
        # CS100A 读取方式1: 直接读取
        # 有些模块需要先发命令
        try:
            bus.write_byte(CS100A_ADDR, 0x01)  # 触发测量
            time.sleep(0.1)
        except:
            pass

        # 读取两个字节
        low = bus.read_byte(CS100A_ADDR)
        high = bus.read_byte(CS100A_ADDR)

        distance = (high << 8) | low

        if distance == 0 or distance > 5000:
            return -1

        return distance

    except Exception as e:
        return -1


def test_cs100a():
    """测试 CS100A"""
    print(f"\n{'='*50}")
    print("测试 CS100A 超声波模块...")
    print(f"{'='*50}")

    try:
        import smbus
        bus = smbus.SMBus(I2C_BUS)

        print(f"[信息] 尝试连接地址 0x{CS100A_ADDR:02X}...")

        try:
            # 测试读取
            data = bus.read_byte(CS100A_ADDR)
            print(f"[成功] 读到数据: {data}")
        except Exception as e:
            print(f"[警告] 直接读取失败: {e}")

        print("\n[信息] 读取 5 次距离数据...")

        for i in range(5):
            dist = read_distance(bus)
            if dist > 0:
                print(f"  第{i+1}次: {dist} mm ({dist/10:.1f} cm)")
            else:
                print(f"  第{i+1}次: 超时")
            time.sleep(0.3)

        bus.close()
        return True

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        return False


def continuous_read():
    """连续读取模式"""
    print(f"\n{'='*50}")
    print("连续测距模式 - 按 Ctrl+C 退出")
    print(f"{'='*50}")

    try:
        import smbus
        bus = smbus.SMBus(I2C_BUS)

        while True:
            dist = read_distance(bus)

            if dist > 0:
                print(f"距离: {dist:4d} mm ({dist/10:5.1f} cm)", end='')

                if dist < 80:
                    print(" [近]", end='')
                elif dist > 150:
                    print(" [远]", end='')
                else:
                    print(" [中]", end='')
                print()
            else:
                print("距离: -- 超时 --")

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[信息] 退出测距模式")
    finally:
        try:
            bus.close()
        except:
            pass


def main():
    """主函数"""
    print("=" * 50)
    print("CS100A 超声波测距 - 飞腾派专用")
    print("功能: I2C初始化 + 设备扫描 + 测距")
    print("=" * 50)

    # 1. 启用 I2C
    if not enable_i2c():
        print("\n[错误] I2C 初始化失败")
        print("请手动启用 I2C:")
        print("  1. 编辑 /boot/config.txt")
        print("  2. 添加: dtparam=i2c_arm=on")
        print("  3. 重启")
        return

    # 2. 扫描 I2C 设备
    devices = scan_i2c_devices(I2C_BUS)

    if not devices:
        print("\n[警告] 未扫描到任何 I2C 设备")
        print("请检查:")
        print("  1. CS100A 接线是否正确")
        print("  2. 5V 电源是否正常")
        print("  3. SDA/SCL 是否接错")
    elif CS100A_ADDR not in devices:
        print(f"\n[警告] 未在地址 0x{CS100A_ADDR:02X} 找到 CS100A")
        print(f"找到的设备: {[hex(d) for d in devices]}")
        print("\n如果列表中有 --，表示该地址被占用(UU)")

    # 3. 测试 CS100A
    test_cs100a()

    # 4. 进入连续读取
    print("\n[信息] 进入连续测距模式...")
    continuous_read()


if __name__ == "__main__":
    main()
