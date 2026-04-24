#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32-CAM 视频流显示程序
使用 urllib 直接读取 MJPEG 流并解析显示
"""

import cv2
import numpy as np
import os
import sys
import urllib.request
import threading
import time
from datetime import datetime


class MJPEGCapture:
    """MJPEG视频流捕获器"""

    def __init__(self, ip, port=81):
        self.ip = ip
        self.port = port
        self.url = f"http://{ip}:{port}/stream"
        self.frame = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.frame_count = 0
        self.error_count = 0

    def _fetch(self):
        """获取视频帧"""
        JPEG_START = b'\xff\xd8'  # JPEG SOI marker
        JPEG_END = b'\xff\xd9'     # JPEG EOI marker

        consecutive_errors = 0

        while self.running:
            try:
                print(f"[INFO] 连接到: {self.url}")
                req = urllib.request.Request(
                    self.url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (ESP32-CAM Stream Client)'
                    }
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    print("[INFO] 连接成功，开始接收视频流")
                    consecutive_errors = 0

                    buffer = bytearray()
                    in_frame = False
                    frame_start_pos = 0

                    while self.running:
                        # 读取数据块
                        chunk = response.read(8192)
                        if not chunk:
                            print("[WARN] 连接断开，重试...")
                            break

                        buffer.extend(chunk)

                        # 防止缓冲区过大
                        if len(buffer) > 100000:
                            print(f"[WARN] 缓冲区过大 ({len(buffer)} bytes)，清理")
                            # 查找最后一个可能的帧开始位置
                            last_start = buffer.rfind(JPEG_START)
                            if last_start > 0:
                                buffer = buffer[last_start:]
                            else:
                                buffer = buffer[-5000:]

                        # 查找JPEG帧
                        while len(buffer) >= 2:
                            if not in_frame:
                                # 查找帧开始
                                start_idx = buffer.find(JPEG_START)
                                if start_idx == -1:
                                    # 没有找到起始标记，清理缓冲区
                                    if len(buffer) > 100:
                                        buffer = buffer[-100:]
                                    break

                                if start_idx > 0:
                                    # 有前缀数据，丢弃
                                    buffer = buffer[start_idx:]
                                    print(f"[DEBUG] 丢弃 {start_idx} bytes 前缀数据")

                                if len(buffer) < 2:
                                    break

                                in_frame = True
                                frame_start_pos = 0
                            else:
                                # 在帧内部，查找帧结束
                                end_idx = buffer.find(JPEG_END, frame_start_pos + 2)
                                if end_idx != -1:
                                    # 找到完整帧
                                    jpg_data = bytes(buffer[:end_idx + 2])

                                    # 解码JPEG
                                    img = cv2.imdecode(
                                        np.frombuffer(jpg_data, np.uint8),
                                        cv2.IMREAD_COLOR
                                    )

                                    if img is not None:
                                        with self.lock:
                                            self.frame = img
                                        self.frame_count += 1
                                        if self.frame_count % 100 == 0:
                                            print(f"[INFO] 已接收 {self.frame_count} 帧")
                                    else:
                                        self.error_count += 1
                                        if self.error_count <= 5:
                                            print(f"[ERROR] JPEG解码失败")

                                    # 清理已处理的缓冲区
                                    buffer = buffer[end_idx + 2:]
                                    in_frame = False
                                else:
                                    # 帧未完成，等待更多数据
                                    # 如果缓冲区积累太多数据但找不到帧结束，可能数据损坏
                                    if len(buffer) > 50000 and not in_frame:
                                        print("[WARN] 缓冲区过大但未找到完整帧，重置")
                                        buffer = buffer[-1000:]
                                        in_frame = False
                                    break

            except urllib.error.HTTPError as e:
                consecutive_errors += 1
                print(f"[ERROR] HTTP错误: {e.code} {e.reason}")
                if consecutive_errors > 3:
                    print("[ERROR] 连接失败次数过多，退出")
                    break
                time.sleep(2)

            except urllib.error.URLError as e:
                consecutive_errors += 1
                print(f"[ERROR] URL错误: {e.reason}")
                if consecutive_errors > 3:
                    print("[ERROR] 连接失败次数过多，退出")
                    break
                time.sleep(2)

            except Exception as e:
                consecutive_errors += 1
                print(f"[ERROR] 异常: {type(e).__name__}: {e}")
                if consecutive_errors > 3:
                    print("[ERROR] 连接失败次数过多，退出")
                    break
                time.sleep(2)

        print("[INFO] 视频流接收线程结束")

    def start(self):
        """启动捕获"""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._fetch, daemon=True)
        self.thread.start()

    def stop(self):
        """停止捕获"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)

    def read(self):
        """读取当前帧"""
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return None

    def is_running(self):
        """检查是否正在运行"""
        return self.running and self.thread is not None and self.thread.is_alive()


def main():
    # 设置显示环境
    display = os.environ.get('DISPLAY', ':0')
    os.environ['DISPLAY'] = display
    print(f"[INFO] 显示环境: {display}")

    # 获取IP和端口
    ip = "192.168.5.1"
    port = 81

    if len(sys.argv) > 1:
        ip = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])

    print("=" * 50)
    print("ESP32-CAM 视频流显示")
    print("=" * 50)
    print(f"URL: http://{ip}:{port}/stream")
    print("按 'q' 退出，按 's' 截图")

    # 启动捕获
    cap = MJPEGCapture(ip, port)

    try:
        cap.start()

        # 等待首帧
        print("[INFO] 等待视频流...")
        for i in range(50):
            frame = cap.read()
            if frame is not None:
                print(f"[SUCCESS] 视频流已连接 (等待 {i * 0.1:.1f} 秒)")
                break
            time.sleep(0.1)
        else:
            print("[ERROR] 无法获取视频流")
            print("[HINT] 请检查: 1) ESP32-CAM是否已启动 2) WiFi是否已连接 3) IP地址是否正确")
            cap.stop()
            return

        # 创建窗口
        window_name = "ESP32-CAM (按 q 退出)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)

        # 主循环
        last_fps_time = time.time()
        fps = 0
        frame_count = 0

        while cap.is_running():
            frame = cap.read()

            if frame is not None:
                # 显示帧率
                frame_count += 1
                current_time = time.time()
                if current_time - last_fps_time >= 1.0:
                    fps = frame_count
                    frame_count = 0
                    last_fps_time = current_time

                # 在画面上显示信息
                display_frame = frame.copy()
                cv2.putText(
                    display_frame,
                    f"FPS: {fps}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
                cv2.putText(
                    display_frame,
                    f"Frames: {cap.frame_count}",
                    (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )

                cv2.imshow(window_name, display_frame)

            # 检查按键
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("[INFO] 用户退出")
                break
            elif key == ord('s') and frame is not None:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_dir = os.path.dirname(os.path.abspath(__file__)) or "."
                path = f"{save_dir}/screenshot_{ts}.jpg"
                cv2.imwrite(path, frame)
                print(f"[INFO] 截图已保存: {path}")

    finally:
        cap.stop()
        cv2.destroyAllWindows()
        print("[INFO] 程序结束")


if __name__ == "__main__":
    main()
