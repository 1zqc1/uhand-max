#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arduino 串口数据读取
功能：读取Arduino输出的超声波测距数据
"""

import serial
import serial.tools.list_ports
import time


def find_arduino_port():
    """自动查找 Arduino 串口"""
    ports = list(serial.tools.list_ports.comports())

    print("可用串口:")
    for i, p in enumerate(ports):
        print(f"  {i+1}. {p.device} - {p.description}")

    if not ports:
        print("[错误] 未找到任何串口设备")
        return None

    # 尝试自动识别 Arduino
    for p in ports:
        if 'Arduino' in p.description or 'CH340' in p.description or 'USB' in p.description:
            print(f"\n[自动选择] {p.device}")
            return p.device

    # 否则选择第一个
    print(f"\n[使用第一个] {ports[0].device}")
    return ports[0].device


def read_serial(port=None, baud=9600):
    """读取串口数据"""
    if port is None:
        port = find_arduino_port()
        if port is None:
            return

    try:
        print(f"\n连接串口 {port} @ {baud} bps...")
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)  # 等待Arduino重置

        print("=" * 50)
        print("开始读取串口数据 (按 Ctrl+C 退出)")
        print("=" * 50)

        line_count = 0
        start_time = time.time()

        while True:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                try:
                    text = data.decode('utf-8', errors='ignore')
                    print(text, end='')
                    line_count += text.count('\n')
                except:
                    pass

            time.sleep(0.1)

    except serial.SerialException as e:
        print(f"[错误] 串口打开失败: {e}")
    except KeyboardInterrupt:
        print("\n\n[信息] 退出程序")
        elapsed = time.time() - start_time
        print(f"读取了 {line_count} 行数据，耗时 {elapsed:.1f} 秒")
    finally:
        try:
            ser.close()
        except:
            pass


def main():
    import sys

    port = None
    baud = 9600

    # 命令行参数
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        baud = int(sys.argv[2])

    read_serial(port, baud)


if __name__ == "__main__":
    main()
