#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32-CAM 视频流显示程序
在飞腾派HDMI显示器上实时显示ESP32-CAM视频

用法:
    python3 esp32_cam_display.py [IP]
    IP: ESP32-CAM的IP地址 (默认: 192.168.5.1)
"""

import cv2
import os
import sys
from datetime import datetime


def main():
    # 自动设置显示环境
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'

    # 获取IP地址
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.5.1"

    print("=" * 50)
    print("ESP32-CAM 视频流显示")
    print("=" * 50)
    print(f"IP: {ip}")

    # 方式1: 直接用OpenCV的VideoCapture
    url = f"http://{ip}/stream"
    print(f"尝试连接: {url}")

    cap = cv2.VideoCapture(url)

    if not cap.isOpened():
        print("[INFO] VideoCapture方式失败，尝试备用方式...")
        cap.release()

        # 方式2: 尝试不同的URL格式
        for path in ["/", "/video", "/mjpeg"]:
            url = f"http://{ip}{path}"
            print(f"[INFO] 尝试: {url}")
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                print(f"[成功] 连接: {url}")
                break

    if not cap.isOpened():
        print("[错误] 无法打开视频流，请检查:")
        print("1. ESP32-CAM是否正常工作")
        print("2. IP地址是否正确")
        print("3. WiFi是否连接")
        return

    print("[成功] 视频流已打开")

    # 创建窗口
    window_name = "ESP32-CAM"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 800, 600)

    frame_count = 0
    save_dir = os.path.dirname(os.path.abspath(__file__)) or "."

    print("[INFO] 按 'q' 退出, 's' 保存截图")

    while True:
        ret, frame = cap.read()

        if ret:
            frame_count += 1

            # 显示帧
            cv2.imshow(window_name, frame)

            # 显示状态
            if frame_count % 30 == 0:
                print(f"[INFO] 显示帧: {frame_count}, 尺寸: {frame.shape}")

        # 按键处理
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("[INFO] 退出")
            break
        elif key == ord('s') and ret:
            # 保存截图
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(save_dir, f"screenshot_{timestamp}.jpg")
            cv2.imwrite(filename, frame)
            print(f"[INFO] 截图已保存: {filename}")

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] 程序已退出")


if __name__ == "__main__":
    main()
