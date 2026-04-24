#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32-CAM 视频流显示程序
通过 urllib 获取MJPEG视频流并显示
"""

import cv2
import numpy
import os
import sys
import urllib.request
import threading
from datetime import datetime


class MJPEGCapture:
    """MJPEG视频流捕获器"""

    def __init__(self, ip):
        self.ip = ip
        self.frame = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

    def _fetch(self):
        """获取视频帧"""
        # 尝试多个可能的URL路径和端口
        urls_to_try = [
            f"http://{self.ip}:81/stream",
            f"http://{self.ip}:81/",
            f"http://{self.ip}/stream",
            f"http://{self.ip}/",
        ]
        url = None

        for test_url in urls_to_try:
            print(f"[INFO] 尝试: {test_url}")
            try:
                req = urllib.request.Request(test_url, headers={'User-Agent': 'Mozilla/5.0'})
                response = urllib.request.urlopen(req, timeout=5)
                url = test_url
                print(f"[成功] 使用: {url}")
                break
            except Exception as e:
                print(f"[失败] {test_url}: {e}")
                continue

        if url is None:
            print("[错误] 所有URL都失败")
            return

        while self.running:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                response = urllib.request.urlopen(req, timeout=10)

                bytes_data = b''
                while self.running:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    bytes_data += chunk

                    # 查找JPEG帧
                    while True:
                        start = bytes_data.find(b'\xff\xd8')
                        end = bytes_data.find(b'\xff\xd9', start + 2 if start != -1 else 0)

                        if start != -1 and end != -1 and end > start:
                            jpg = bytes_data[start:end + 2]
                            bytes_data = bytes_data[end + 2:]

                            img = cv2.imdecode(
                                numpy.frombuffer(jpg, numpy.uint8),
                                cv2.IMREAD_COLOR
                            )

                            if img is not None:
                                with self.lock:
                                    self.frame = img
                        else:
                            break

            except Exception as e:
                print(f"[错误] 连接断开: {e}")
                if self.running:
                    threading.Event().wait(2)

    def start(self):
        """启动捕获"""
        self.running = True
        self.thread = threading.Thread(target=self._fetch, daemon=True)
        self.thread.start()
        print(f"[INFO] 连接 {self.ip}")

    def stop(self):
        """停止捕获"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def read(self):
        """读取当前帧"""
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return None


def main():
    # 设置显示环境
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'

    # 获取IP
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.5.1"

    print("=" * 50)
    print("ESP32-CAM 视频流显示")
    print("=" * 50)
    print(f"IP: {ip}")

    # 启动捕获
    cap = MJPEGCapture(ip)
    cap.start()

    # 等待首帧
    print("[INFO] 等待视频...")
    for _ in range(50):
        if cap.read() is not None:
            break
        threading.Event().wait(0.1)
    else:
        print("[错误] 无法获取视频流")
        cap.stop()
        return

    print("[成功] 视频已连接")

    # 创建窗口
    window = "ESP32-CAM"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 800, 600)

    count = 0
    save_dir = os.path.dirname(os.path.abspath(__file__)) or "."

    print("[INFO] 'q'退出 's'截图")

    while True:
        frame = cap.read()

        if frame is not None:
            count += 1
            cv2.imshow(window, frame)
            if count % 60 == 0:
                print(f"[INFO] 帧: {count}")

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s') and frame is not None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            cv2.imwrite(f"{save_dir}/screenshot_{ts}.jpg", frame)
            print(f"[INFO] 已保存截图")

    cap.stop()
    cv2.destroyAllWindows()
    print("[INFO] 完成")


if __name__ == "__main__":
    main()
