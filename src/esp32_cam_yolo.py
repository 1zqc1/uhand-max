#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32-CAM + YOLO 目标检测程序
使用 OpenCV DNN 模块加载 ONNX 模型进行实时目标检测
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

    def _fetch(self):
        """获取视频帧"""
        JPEG_START = b'\xff\xd8'
        JPEG_END = b'\xff\xd9'

        while self.running:
            try:
                print(f"[INFO] 连接到: {self.url}")
                req = urllib.request.Request(
                    self.url,
                    headers={'User-Agent': 'Mozilla/5.0 (ESP32-CAM Stream Client)'}
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    print("[INFO] 连接成功，开始接收视频流")

                    buffer = bytearray()
                    in_frame = False

                    while self.running:
                        chunk = response.read(8192)
                        if not chunk:
                            break

                        buffer.extend(chunk)

                        if len(buffer) > 100000:
                            last_start = buffer.rfind(JPEG_START)
                            if last_start > 0:
                                buffer = buffer[last_start:]
                            else:
                                buffer = buffer[-5000:]

                        while len(buffer) >= 2:
                            if not in_frame:
                                start_idx = buffer.find(JPEG_START)
                                if start_idx == -1:
                                    if len(buffer) > 100:
                                        buffer = buffer[-100:]
                                    break

                                if start_idx > 0:
                                    buffer = buffer[start_idx:]

                                if len(buffer) < 2:
                                    break

                                in_frame = True
                            else:
                                end_idx = buffer.find(JPEG_END)
                                if end_idx != -1:
                                    jpg_data = bytes(buffer[:end_idx + 2])

                                    img = cv2.imdecode(
                                        np.frombuffer(jpg_data, np.uint8),
                                        cv2.IMREAD_COLOR
                                    )

                                    if img is not None:
                                        with self.lock:
                                            self.frame = img
                                        self.frame_count += 1

                                    buffer = buffer[end_idx + 2:]
                                    in_frame = False
                                else:
                                    if len(buffer) > 50000:
                                        buffer = buffer[-1000:]
                                        in_frame = False
                                    break

            except Exception as e:
                print(f"[ERROR] {type(e).__name__}: {e}")
                if self.running:
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
        return self.running and self.thread is not None and self.thread.is_alive()


class YOLODetector:
    """YOLO 目标检测器"""

    # COCO 数据集 80 类名称
    CLASSES = [
        'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
        'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
        'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
        'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
        'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
        'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
        'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
        'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
        'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book',
        'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
    ]

    # 检测类别过滤（设为空则检测所有类别）
    # 例如只检测人、车: ['person', 'car', 'motorcycle']
    FILTER_CLASSES = []

    def __init__(self, model_path=None, conf_threshold=0.5, nms_threshold=0.4):
        """
        初始化 YOLO 检测器

        Args:
            model_path: ONNX 模型路径，None 则使用默认路径
            conf_threshold: 置信度阈值
            nms_threshold: NMS 阈值
        """
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold

        # 尝试查找模型
        if model_path is None:
            model_path = self._find_model()

        self.net = None
        self.model_path = model_path

        if model_path and os.path.exists(model_path):
            print(f"[INFO] 加载 YOLO 模型: {model_path}")
            self.net = cv2.dnn.readNet(model_path)
            self._setup_backend()
        else:
            print(f"[WARN] YOLO 模型未找到: {model_path}")
            print("[INFO] 将使用颜色检测作为备选方案")
            self.net = None

        # 获取输出层信息
        self.output_layers = None
        self.input_size = (416, 416)  # YOLOv3/v4 默认输入尺寸

        if self.net:
            self._get_output_layers()

    def _find_model(self):
        """查找 YOLO 模型"""
        possible_paths = [
            'yolov3.onnx',
            'yolov4.onnx',
            'yolov3-tiny.onnx',
            'yolov4-tiny.onnx',
            'models/yolov3.onnx',
            'models/yolov4.onnx',
            '/usr/local/share/yolov3.onnx',
            '/usr/share/yolo/yolov3.onnx',
        ]

        script_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths.extend([
            os.path.join(script_dir, 'yolov3.onnx'),
            os.path.join(script_dir, 'models', 'yolov3.onnx'),
        ])

        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    def _setup_backend(self):
        """设置推理后端"""
        try:
            # 尝试使用 CUDA (需要 OpenCV 编译时支持)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
            print("[INFO] 使用 CUDA 加速")
        except:
            try:
                # 尝试使用 OpenVINO (Intel)
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_INFERENCE_ENGINE)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_MYRIAD)
                print("[INFO] 使用 Intel Neural Compute Stick 加速")
            except:
                # 回退到 CPU
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                print("[INFO] 使用 CPU 推理")

    def _get_output_layers(self):
        """获取输出层名称"""
        try:
            layer_names = self.net.getLayerNames()
            out_layers_idx = self.net.getUnconnectedOutLayers()
            self.output_layers = [layer_names[i[0] - 1] for i in out_layers_idx]
            print(f"[INFO] 输出层: {self.output_layers}")
        except:
            self.output_layers = None

    def detect_color(self, frame):
        """
        颜色检测备选方案（当 YOLO 模型不可用时）
        检测红色、蓝色、绿色的物体
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 定义颜色范围
        colors = {
            'Red': ([0, 100, 100], [10, 255, 255]),
            'Blue': ([100, 100, 100], [130, 255, 255]),
            'Green': ([40, 100, 100], [80, 255, 255]),
            'Yellow': ([20, 100, 100], [30, 255, 255]),
        }

        detections = []
        for color_name, (lower, upper) in colors.items():
            lower = np.array(lower, dtype=np.uint8)
            upper = np.array(upper, dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 1000:  # 过滤小区域
                    x, y, w, h = cv2.boundingRect(cnt)
                    detections.append({
                        'class': color_name,
                        'confidence': 0.8,
                        'bbox': (x, y, x + w, y + h)
                    })

        return detections

    def detect(self, frame):
        """
        执行目标检测

        Args:
            frame: 输入图像 (BGR格式)

        Returns:
            detections: 检测结果列表，每个元素包含 class, confidence, bbox
        """
        if self.net is None:
            return self.detect_color(frame)

        blob = cv2.dnn.blobFromImage(
            frame,
            1/255.0,
            self.input_size,
            (0, 0, 0),
            swapRB=True,
            crop=False
        )

        self.net.setInput(blob)

        if self.output_layers:
            outs = self.net.forward(self.output_layers)
        else:
            outs = self.net.forward()

        return self._post_process(outs, frame.shape)

    def _post_process(self, outs, image_shape):
        """后处理网络输出"""
        height, width = image_shape[:2]
        class_ids = []
        confidences = []
        boxes = []

        for out in outs:
            for detection in out:
                if len(detection) < 5:
                    continue

                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]

                if confidence < self.conf_threshold:
                    continue

                # 解析边界框
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)

                x = int(center_x - w / 2)
                y = int(center_y - h / 2)

                class_name = self.CLASSES[class_id] if class_id < len(self.CLASSES) else f'class_{class_id}'

                # 类别过滤
                if self.FILTER_CLASSES and class_name not in self.FILTER_CLASSES:
                    continue

                class_ids.append(class_name)
                confidences.append(float(confidence))
                boxes.append((x, y, x + w, y + h))

        # NMS 非极大值抑制
        indices = []
        if boxes:
            indices = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_threshold, self.nms_threshold)

        detections = []
        try:
            for i in indices:
                if isinstance(i, (list, tuple, np.ndarray)):
                    i = i[0]
                detections.append({
                    'class': class_ids[i],
                    'confidence': confidences[i],
                    'bbox': boxes[i]
                })
        except:
            pass

        return detections

    def draw_detection(self, frame, detection):
        """在图像上绘制单个检测结果"""
        x1, y1, x2, y2 = detection['bbox']
        class_name = detection['class']
        confidence = detection['confidence']

        # 颜色映射
        color_map = {
            'person': (255, 0, 0),      # 蓝色
            'car': (0, 255, 255),       # 黄色
            'motorcycle': (0, 255, 0),  # 绿色
            'bicycle': (255, 255, 0),   # 青色
            'dog': (128, 0, 255),       # 紫色
            'cat': (0, 128, 255),       # 橙色
        }
        color = color_map.get(class_name, (0, 255, 255))

        # 绘制边界框
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # 绘制标签背景
        label = f'{class_name} {confidence:.2f}'
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - label_size[1] - 4), (x1 + label_size[0], y1), color, -1)

        # 绘制标签文字
        cv2.putText(frame, label, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return frame


def main():
    # 参数解析
    ip = "192.168.5.1"
    port = 81
    model_path = None
    conf_threshold = 0.5
    nms_threshold = 0.4
    show_fps = True
    filter_classes = []

    # 命令行参数
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    if len(sys.argv) > 3:
        model_path = sys.argv[3]

    print("=" * 50)
    print("ESP32-CAM + YOLO 目标检测")
    print("=" * 50)
    print(f"视频流: http://{ip}:{port}/stream")
    print(f"模型: {model_path or '未指定 (将使用颜色检测)'}")
    print("=" * 50)
    print("按键说明:")
    print("  q - 退出程序")
    print("  s - 截图")
    print("  f - 切换 FPS 显示")
    print("  d - 切换调试信息")
    print("=" * 50)

    # 初始化检测器
    detector = YOLODetector(
        model_path=model_path,
        conf_threshold=conf_threshold,
        nms_threshold=nms_threshold
    )

    # 初始化视频捕获
    cap = MJPEGCapture(ip, port)

    try:
        cap.start()

        # 等待视频流连接
        print("[INFO] 等待视频流...")
        for i in range(50):
            frame = cap.read()
            if frame is not None:
                print(f"[SUCCESS] 视频流已连接 ({i * 0.1:.1f}s)")
                break
            time.sleep(0.1)
        else:
            print("[ERROR] 无法获取视频流")
            cap.stop()
            return

        # 创建窗口
        window_name = "ESP32-CAM YOLO (按 q 退出)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)

        # 统计信息
        frame_count = 0
        fps = 0
        last_time = time.time()
        debug_mode = False

        # 主循环
        while cap.is_running():
            frame = cap.read()

            if frame is not None:
                frame_count += 1

                # YOLO 检测
                detections = detector.detect(frame)

                # 绘制检测结果
                for det in detections:
                    frame = detector.draw_detection(frame, det)

                # 计算 FPS
                current_time = time.time()
                if current_time - last_time >= 1.0:
                    fps = frame_count
                    frame_count = 0
                    last_time = current_time

                # 显示 FPS 和检测数量
                if show_fps:
                    info_text = f"FPS: {fps} | 检测: {len(detections)}"
                    cv2.putText(frame, info_text, (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # 调试信息
                if debug_mode:
                    cv2.putText(frame, f"帧: {cap.frame_count}", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    if detector.net:
                        cv2.putText(frame, "YOLO: 已加载", (10, 85),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    else:
                        cv2.putText(frame, "YOLO: 颜色检测", (10, 85),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

                # 显示图像
                cv2.imshow(window_name, frame)

            # 按键处理
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s') and frame is not None:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_dir = os.path.dirname(os.path.abspath(__file__)) or "."
                path = f"{save_dir}/yolo_screenshot_{ts}.jpg"
                cv2.imwrite(path, frame)
                print(f"[INFO] 截图已保存: {path}")
            elif key == ord('f'):
                show_fps = not show_fps
            elif key == ord('d'):
                debug_mode = not debug_mode

    finally:
        cap.stop()
        cv2.destroyAllWindows()
        print("[INFO] 程序结束")


if __name__ == "__main__":
    main()
