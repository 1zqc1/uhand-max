#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32-CAM + YOLO 目标检测程序
支持 OpenCV DNN 和 ONNX Runtime 两种后端
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

    def __init__(self, model_path=None, conf_threshold=0.5, nms_threshold=0.4):
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.model_path = model_path
        self.net = None
        self.session = None
        self.input_name = None
        self.output_name = None
        self.input_size = (416, 416)
        self.using_onnx_runtime = False

        # 尝试查找模型
        if model_path is None:
            model_path = self._find_model()

        if model_path and os.path.exists(model_path):
            print(f"[INFO] 模型路径: {model_path}")
            self._load_model(model_path)
        else:
            print(f"[WARN] 模型未找到: {model_path}")
            print("[INFO] 将使用颜色检测作为备选方案")

    def _find_model(self):
        """查找 YOLO 模型"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            'yolov3-tiny.onnx',
            'yolov4-tiny.onnx',
            'yolov5s.onnx',
            'yolov3.onnx',
            'yolov4.onnx',
            'models/yolov3-tiny.onnx',
            'models/yolov4-tiny.onnx',
            'models/yolov5s.onnx',
            os.path.join(script_dir, 'yolov3-tiny.onnx'),
            os.path.join(script_dir, 'yolov4-tiny.onnx'),
            os.path.join(script_dir, 'yolov5s.onnx'),
            os.path.join(script_dir, 'models', 'yolov3-tiny.onnx'),
            os.path.join(script_dir, 'models', 'yolov4-tiny.onnx'),
            os.path.join(script_dir, 'models', 'yolov5s.onnx'),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    def _load_model(self, model_path):
        """加载模型"""
        # 尝试使用 ONNX Runtime
        try:
            import onnxruntime as ort
            print("[INFO] 使用 ONNX Runtime")
            self.session = ort.InferenceSession(
                model_path,
                providers=['CPUExecutionProvider']
            )
            self.using_onnx_runtime = True

            # 获取输入输出名称
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            print(f"[INFO] 输入: {self.input_name}, 输出: {self.output_name}")
            return

        except ImportError:
            print("[WARN] ONNX Runtime 未安装，尝试 OpenCV DNN")
        except Exception as e:
            print(f"[WARN] ONNX Runtime 加载失败: {e}，尝试 OpenCV DNN")

        # 回退到 OpenCV DNN
        try:
            print("[INFO] 使用 OpenCV DNN")
            self.net = cv2.dnn.readNet(model_path)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

            # 获取输出层
            layer_names = self.net.getLayerNames()
            out_layers_idx = self.net.getUnconnectedOutLayers()
            self.output_layers = [layer_names[i[0] - 1] for i in out_layers_idx]
            print(f"[INFO] 输出层: {self.output_layers}")
        except Exception as e:
            print(f"[ERROR] OpenCV DNN 也加载失败: {e}")
            self.net = None

    def detect(self, frame):
        """执行目标检测"""
        if self.session:
            return self._detect_onnx_runtime(frame)
        elif self.net:
            return self._detect_opencv_dnn(frame)
        else:
            return self.detect_color(frame)

    def _detect_onnx_runtime(self, frame):
        """使用 ONNX Runtime 检测"""
        # 预处理
        blob = cv2.dnn.blobFromImage(
            frame,
            1/255.0,
            self.input_size,
            (0, 0, 0),
            swapRB=True,
            crop=False
        )

        # 推理
        outs = self.session.run(
            [self.output_name],
            {self.input_name: blob}
        )

        return self._post_process_yolov5(outs[0], frame.shape)

    def _detect_opencv_dnn(self, frame):
        """使用 OpenCV DNN 检测"""
        blob = cv2.dnn.blobFromImage(
            frame,
            1/255.0,
            self.input_size,
            (0, 0, 0),
            swapRB=True,
            crop=False
        )

        self.net.setInput(blob)
        outs = self.net.forward(self.output_layers)

        return self._post_process_yolov3(outs, frame.shape)

    def _post_process_yolov5(self, outputs, image_shape):
        """后处理 YOLOv5 格式输出 (1, 25200, 85)"""
        height, width = image_shape[:2]
        detections = []

        # YOLOv5 输出格式: [batch, 25200, 85] 其中85 = 4(box) + 1(conf) + 80(classes)
        if len(outputs.shape) == 3:
            outputs = outputs[0]  # 去掉batch维度

        # 遍历所有检测框
        for detection in outputs:
            if len(detection) < 85:
                continue

            # 解析: x, y, w, h, obj_conf, class1_conf, class2_conf, ...
            x, y, w, h = detection[0:4]
            obj_conf = detection[4]

            # 获取类别置信度
            class_scores = detection[5:]
            class_id = np.argmax(class_scores)
            class_conf = class_scores[class_id]

            # 最终置信度
            confidence = obj_conf * class_conf

            if confidence < self.conf_threshold:
                continue

            # 转换为边界框坐标
            x1 = int((x - w/2) * width)
            y1 = int((y - h/2) * height)
            x2 = int((x + w/2) * width)
            y2 = int((y + h/2) * height)

            class_name = self.CLASSES[class_id] if class_id < len(self.CLASSES) else f'class_{class_id}'

            detections.append({
                'class': class_name,
                'confidence': float(confidence),
                'bbox': (x1, y1, x2, y2)
            })

        # NMS
        return self._apply_nms(detections)

    def _post_process_yolov3(self, outputs, image_shape):
        """后处理 YOLOv3/v4 格式输出"""
        height, width = image_shape[:2]
        class_ids = []
        confidences = []
        boxes = []

        for out in outputs:
            for detection in out:
                if len(detection) < 85:
                    continue

                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]

                if confidence < self.conf_threshold:
                    continue

                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)

                x = int(center_x - w / 2)
                y = int(center_y - h / 2)

                class_name = self.CLASSES[class_id] if class_id < len(self.CLASSES) else f'class_{class_id}'

                class_ids.append(class_name)
                confidences.append(float(confidence))
                boxes.append((x, y, x + w, y + h))

        indices = self._apply_nms(list(zip(class_ids, confidences, boxes)))
        detections = []
        for i in indices:
            if isinstance(i, (list, tuple, np.ndarray)):
                i = i[0]
            detections.append({
                'class': class_ids[i],
                'confidence': confidences[i],
                'bbox': boxes[i]
            })

        return detections

    def _apply_nms(self, detections):
        """应用 NMS"""
        if not detections:
            return []

        boxes = [d['bbox'] for d in detections]
        scores = [d['confidence'] for d in detections]

        try:
            indices = cv2.dnn.NMSBoxes(boxes, scores, self.conf_threshold, self.nms_threshold)
            if isinstance(indices, np.ndarray):
                indices = indices.flatten()
            return [detections[i] for i in indices]
        except:
            return detections

    def detect_color(self, frame):
        """颜色检测备选方案"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

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
                if area > 1000:
                    x, y, w, h = cv2.boundingRect(cnt)
                    detections.append({
                        'class': color_name,
                        'confidence': 0.8,
                        'bbox': (x, y, x + w, y + h)
                    })

        return detections

    def draw_detection(self, frame, detection):
        """绘制检测结果"""
        x1, y1, x2, y2 = detection['bbox']
        class_name = detection['class']
        confidence = detection['confidence']

        color_map = {
            'person': (255, 0, 0),
            'car': (0, 255, 255),
            'motorcycle': (0, 255, 0),
            'bicycle': (255, 255, 0),
            'dog': (128, 0, 255),
            'cat': (0, 128, 255),
        }
        color = color_map.get(class_name, (0, 255, 255))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label = f'{class_name} {confidence:.2f}'
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1 - label_size[1] - 4), (x1 + label_size[0], y1), color, -1)
        cv2.putText(frame, label, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return frame


def main():
    ip = "192.168.5.1"
    port = 81
    model_path = None

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
    print(f"模型: {model_path or '未指定'}")
    print("=" * 50)

    detector = YOLODetector(model_path=model_path)

    cap = MJPEGCapture(ip, port)

    try:
        cap.start()

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

        window_name = "ESP32-CAM YOLO (按 q 退出)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)

        frame_count = 0
        fps = 0
        last_time = time.time()
        show_fps = True

        while cap.is_running():
            frame = cap.read()

            if frame is not None:
                frame_count += 1

                detections = detector.detect(frame)

                for det in detections:
                    frame = detector.draw_detection(frame, det)

                current_time = time.time()
                if current_time - last_time >= 1.0:
                    fps = frame_count
                    frame_count = 0
                    last_time = current_time

                if show_fps:
                    info_text = f"FPS: {fps} | 检测: {len(detections)}"
                    cv2.putText(frame, info_text, (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                    # 显示当前检测模式
                    if detector.session:
                        mode_text = "ONNX Runtime"
                    elif detector.net:
                        mode_text = "OpenCV DNN"
                    else:
                        mode_text = "颜色检测"
                    cv2.putText(frame, mode_text, (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

                cv2.imshow(window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s') and frame is not None:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = f"screenshot_{ts}.jpg"
                cv2.imwrite(path, frame)
                print(f"[INFO] 截图已保存: {path}")

    finally:
        cap.stop()
        cv2.destroyAllWindows()
        print("[INFO] 程序结束")


if __name__ == "__main__":
    main()
