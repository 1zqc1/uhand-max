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

    # 飞腾派可能使用不同的 I2C 总线号
    for bus in [0, 1, 2]:
        if os.path.exists(f'/dev/i2c-{bus}'):
            print(f"[成功] 使用 I2C-{bus}")
            return True

    print("[错误] 未找到任何 I2C 设备")
    print("请检查内核配置是否支持 I2C")
    return False


def scan_i2c_devices(bus_num=1):
    """扫描 I2C 总线上的所有设备"""
    device_path = f"/dev/i2c-{bus_num}"
    if not os.path.exists(device_path):
        print(f"[错误] {device_path} 不存在")
        return []

    print(f"\n{'='*50}")
    print(f"扫描 I2C-{bus_num} 总线上的设备...")
    print(f"{'='*50}")

    # 使用 i2cdetect 命令
    ret, out, err = run_cmd(f"i2cdetect -y {bus_num} 2>&1")
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

    return []


def read_cs100a_distance(bus, addr):
    """
    读取 CS100A 距离
    根据 Arduino BitBang I2C 方式:
    1. 发送 start + 地址(W) + 寄存器(0x00) + stop
    2. 等待 15ms
    3. 发送 start + 地址(R) + 读两个字节 + stop
    4. 返回 (高字节 << 8) | 低字节
    """
    try:
        # 先写入寄存器地址 0x00
        bus.write_byte(addr, 0x00)
        time.sleep(0.015)  # 等待 15ms

        # 读取两个字节
        low = bus.read_byte(addr)
        high = bus.read_byte(addr)

        distance = (high << 8) | low

        # 有效距离范围: 10mm - 4000mm
        if 10 <= distance <= 4000:
            return distance
        else:
            return -1

    except Exception as e:
        return -1


def try_multiple_addrs():
    """尝试多个可能的地址读取 CS100A"""
    print(f"\n{'='*50}")
    print("尝试多个 I2C 地址...")
    print(f"{'='*50}")

    # CS100A 常用地址
    possible_addrs = [0x77, 0x76, 0x70, 0x78, 0x57, 0x58]

    found_device = None

    for addr in possible_addrs:
        print(f"\n尝试地址 0x{addr:02X}...")
        try:
            import smbus
            bus = smbus.SMBus(I2C_BUS)

            # 尝试读取
            data = read_cs100a_distance(bus, addr)

            if data > 0:
                print(f"[成功] 地址 0x{addr:02X} 读到距离: {data} mm")
                found_device = addr
                bus.close()
                return addr, bus
            else:
                print(f"[失败] 地址 0x{addr:02X} 未找到有效数据")

            bus.close()
        except Exception as e:
            print(f"[失败] 地址 0x{addr:02X} 错误: {e}")

    return None, None


def continuous_read(addr, bus):
    """连续读取模式"""
    print(f"\n{'='*50}")
    print(f"连续测距模式 (地址: 0x{addr:02X}) - 按 Ctrl+C 退出")
    print(f"{'='*50}")

    success_count = 0
    fail_count = 0

    try:
        while True:
            dist = read_cs100a_distance(bus, addr)

            if dist > 0:
                success_count += 1
                fail_count = 0
                print(f"距离: {dist:4d} mm ({dist/10:5.1f} cm)", end='')

                if dist < 80:
                    print(" [近]", end='')
                elif dist > 150:
                    print(" [远]", end='')
                else:
                    print(" [中]", end='')
                print(f" [成功率: {success_count}/{success_count+fail_count}]")
            else:
                fail_count += 1
                print(f"距离: -- 超时 -- [成功率: {success_count}/{success_count+fail_count}]")

            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n[信息] 退出测距模式")
        print(f"总读取: 成功 {success_count} 次, 失败 {fail_count} 次")
    finally:
        try:
            bus.close()
        except:
            pass


def main():
    """主函数"""
    print("=" * 50)
    print("CS100A 超声波测距 - 飞腾派专用")
    print("功能: I2C初始化 + 地址扫描 + 测距")
    print("=" * 50)

    # 1. 启用 I2C
    if not enable_i2c():
        print("\n[错误] I2C 初始化失败")
        return

    # 2. 扫描 I2C 设备
    devices = scan_i2c_devices(I2C_BUS)

    if not devices:
        print("\n[警告] 未扫描到任何 I2C 设备")
        print("\n请检查:")
        print("  1. CS100A 接线是否正确 (SDA/SCL)")
        print("  2. 5V 电源是否正常")
        print("  3. GND 是否连接")
    else:
        print(f"\n找到 {len(devices)} 个设备: {[hex(d) for d in devices]}")

        if CS100A_ADDR not in devices:
            print(f"\n[注意] 未在默认地址 0x{CS100A_ADDR:02X} 找到设备")
            print("将尝试其他地址...")

    # 3. 尝试多个地址
    addr, bus = try_multiple_addrs()

    if addr is None:
        print("\n[错误] 未能找到 CS100A 设备")
        print("\n可能原因:")
        print("  1. CS100A 地址不是常见的 0x77")
        print("  2. 接线错误 (SDA/SCL 互换)")
        print("  3. 设备损坏或未供电")
        return

    # 4. 进入连续读取
    print(f"\n[成功] 找到 CS100A (地址: 0x{addr:02X})")
    continuous_read(addr, bus)


if __name__ == "__main__":
    main()
