#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32-CAM 视频流显示程序
在飞腾派HDMI显示器上实时显示ESP32-CAM视频

用法:
    python3 esp32_cam_display.py [IP]

    IP: ESP32-CAM的IP地址 (默认: 192.168.5.1)

按 'q' 退出
按 's' 保存截图
"""

import cv2
import numpy as np
import threading
import time
import sys
import os
from datetime import datetime

# ESP32-CAM默认IP地址
DEFAULT_IP = "192.168.5.1"

# 可能的视频流URL路径（尝试列表）
STREAM_PATHS = [
    "/stream",
    "/",
    "/video",
    "/mjpeg/stream",
    "/camera stream",
]


class MJPEGStream:
    """MJPEG视频流接收器"""

    def __init__(self, ip, paths=None):
        self.ip = ip
        self.paths = paths or STREAM_PATHS
        self.url = None
        self.frame = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

    def _try_connect(self):
        """尝试连接可用的视频流URL"""
        import urllib.request

        for path in self.paths:
            url = f"http://{self.ip}{path}"
            print(f"[INFO] 尝试: {url}")
            try:
                stream = urllib.request.urlopen(url, timeout=5)
                print(f"[INFO] 连接成功: {url}")
                return stream, url
            except Exception as e:
                print(f"[INFO] 失败: {url} - {e}")
                continue
        return None, None

    def _fetch_stream(self):
        """后台线程持续获取视频流"""
        import urllib.request

        while self.running:
            if self.url is None:
                stream_obj, url = self._try_connect()
                if stream_obj is None:
                    print("[错误] 无法连接到视频流，请检查ESP32-CAM是否正常工作")
                    time.sleep(3)
                    continue
                self.url = url

            try:
                stream = urllib.request.urlopen(self.url, timeout=10)
                bytes_data = bytes()

                while self.running:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    bytes_data += chunk

                    # 查找JPEG帧
                    while True:
                        a = bytes_data.find(b'\xff\xd8')  # JPEG开始
                        b = bytes_data.find(b'\xff\xd9')  # JPEG结束

                        if a != -1 and b != -1 and b > a:
                            jpg = bytes_data[a:b+2]
                            bytes_data = bytes_data[b+2:]

                            img = cv2.imdecode(
                                np.frombuffer(jpg, dtype=np.uint8),
                                cv2.IMREAD_COLOR
                            )

                            if img is not None:
                                with self.lock:
                                    self.frame = img
                        else:
                            break

            except Exception as e:
                print(f"[错误] 连接断开: {e}")
                self.url = None  # 重置URL以尝试重新连接
                if self.running:
                    time.sleep(2)

    def start(self):
        """启动视频流"""
        self.running = True
        self.thread = threading.Thread(target=self._fetch_stream, daemon=True)
        self.thread.start()
        print(f"[INFO] 正在连接: {self.ip}")

    def stop(self):
        """停止视频流"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("[INFO] 视频流已停止")

    def get_frame(self):
        """获取当前帧"""
        with self.lock:
            return self.frame.copy() if self.frame is not None else None


def save_screenshot(frame, save_dir=None):
    """保存截图"""
    if save_dir is None:
        save_dir = os.path.dirname(os.path.abspath(__file__)) or "."
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(save_dir, f"screenshot_{timestamp}.jpg")
    cv2.imwrite(filename, frame)
    print(f"[INFO] 截图已保存: {filename}")
    return filename


def main():
    # 检查显示环境
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'
        print("[INFO] 已设置 DISPLAY=:0")

    # 获取IP地址参数
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    else:
        ip = DEFAULT_IP

    print("=" * 60)
    print("ESP32-CAM 视频流显示程序")
    print("=" * 60)
    print(f"ESP32-CAM IP: {ip}")
    print("-" * 60)
    print("按键说明:")
    print("  'q' - 退出程序")
    print("  's' - 保存截图")
    print("  'f' - 切换全屏模式")
    print("=" * 60)

    # 创建视频流
    stream = MJPEGStream(ip)
    stream.start()

    # 等待首帧
    print("[INFO] 等待视频流...")
    for _ in range(30):  # 最多等待3秒
        if stream.get_frame() is not None:
            break
        time.sleep(0.1)

    # 创建窗口
    window_name = "ESP32-CAM - Phytium Pi"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 800, 600)

    fullscreen = False

    try:
        while True:
            frame = stream.get_frame()

            if frame is not None:
                # 显示帧
                cv2.imshow(window_name, frame)

                # 添加信息叠加（部分OpenCV版本不支持displayOverlay）
                try:
                    info_text = f"ESP32-CAM: {ip} | Press 'q' to quit"
                    cv2.displayOverlay(window_name, info_text, 3000)
                except AttributeError:
                    pass  # 忽略不支持的版本

            # 等待按键
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                print("[INFO] 用户退出")
                break

            elif key == ord('s'):
                if frame is not None:
                    save_screenshot(frame)

            elif key == ord('f'):
                fullscreen = not fullscreen
                if fullscreen:
                    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    print("[INFO] 全屏模式")
                else:
                    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(window_name, 800, 600)
                    print("[INFO] 窗口模式")

    except KeyboardInterrupt:
        print("\n[INFO] 用户中断")

    finally:
        stream.stop()
        cv2.destroyAllWindows()
        print("[INFO] 程序已退出")


if __name__ == "__main__":
    main()
