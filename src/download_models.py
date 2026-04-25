#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO 模型下载和转换工具
在PC上运行此脚本下载并转换模型
"""

import os
import sys
import urllib.request

# 模型配置
MODELS = {
    'yolov3-tiny': {
        'weights_url': 'https://pjreddie.com/media/files/yolov3-tiny.weights',
        'cfg_url': 'https://raw.githubusercontent.com/pjreddie/darknet/master/cfg/yolov3-tiny.cfg',
        'names_url': 'https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names',
        'filename': 'yolov3-tiny.weights',
        'cfg_file': 'yolov3-tiny.cfg',
        'names_file': 'coco.names',
    },
    'yolov4-tiny': {
        'weights_url': 'https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v4_pre/yolov4-tiny.weights',
        'cfg_url': 'https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg',
        'names_url': 'https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names',
        'filename': 'yolov4-tiny.weights',
        'cfg_file': 'yolov4-tiny.cfg',
        'names_file': 'coco.names',
    },
    'yolov5s': {  # 较新且效果好的模型
        'onnx_url': 'https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx',
        'filename': 'yolov5s.onnx',
    },
}


def download_file(url, dest_path, show_progress=True):
    """下载文件"""
    if os.path.exists(dest_path):
        print(f"[SKIP] 文件已存在: {dest_path}")
        return True

    print(f"[DOWN] {url}")
    print(f"[SAVE] -> {dest_path}")

    try:
        def reporthook(block_num, block_size, total_size):
            if show_progress and total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, downloaded * 100 // total_size)
                if block_num % 50 == 0:
                    print(f"\r  进度: {percent}% ({downloaded//1024}KB / {total_size//1024}KB)", end='')

        urllib.request.urlretrieve(url, dest_path, reporthook)
        print("\n[OK] 下载完成")
        return True
    except Exception as e:
        print(f"\n[ERROR] 下载失败: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def download_yolov3_tiny():
    """下载 YOLOv3-tiny 模型"""
    model = MODELS['yolov3-tiny']
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(script_dir, 'models')
    os.makedirs(model_dir, exist_ok=True)

    print("=" * 50)
    print("下载 YOLOv3-tiny 模型")
    print("=" * 50)

    # 下载权重
    weights_path = os.path.join(model_dir, model['filename'])
    download_file(model['weights_url'], weights_path)

    # 下载配置文件
    cfg_path = os.path.join(model_dir, model['cfg_file'])
    download_file(model['cfg_url'], cfg_path)

    # 下载类别名称
    names_path = os.path.join(model_dir, model['names_file'])
    download_file(model['names_url'], names_path)

    print("\n" + "=" * 50)
    print("下载完成！")
    print(f"模型位置: {model_dir}")
    print("=" * 50)
    return model_dir


def download_yolov5s():
    """下载 YOLOv5s ONNX 模型"""
    model = MODELS['yolov5s']
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(script_dir, 'models')
    os.makedirs(model_dir, exist_ok=True)

    print("=" * 50)
    print("下载 YOLOv5s ONNX 模型")
    print("=" * 50)

    onnx_path = os.path.join(model_dir, model['filename'])
    success = download_file(model['onnx_url'], onnx_path)

    if success:
        print("\n" + "=" * 50)
        print("下载完成！")
        print(f"模型位置: {onnx_path}")
        print("=" * 50)
    return model_dir if success else None


def convert_to_onnx():
    """
    将 Darknet 格式转换为 ONNX
    需要先安装: pip install onnx onnxruntime opencv-python
    """
    try:
        import torch
        import torchvision
    except ImportError:
        print("[ERROR] 需要安装 torch: pip install torch torchvision")
        return False

    print("=" * 50)
    print("转换 Darknet -> ONNX")
    print("=" * 50)

    # 这里需要完整的转换代码
    # 由于转换较复杂，建议使用预编译的 ONNX 模型
    print("[HINT] 建议直接下载 ONNX 格式模型")
    return False


def main():
    print("YOLO 模型下载工具")
    print("=" * 50)
    print("1. 下载 YOLOv3-tiny (Darknet格式)")
    print("2. 下载 YOLOv5s ONNX (直接可用)")
    print("=" * 50)

    choice = input("请选择 (1/2): ").strip()

    if choice == '1':
        download_yolov3_tiny()
    elif choice == '2':
        download_yolov5s()
    else:
        print("[ERROR] 无效选择")


if __name__ == "__main__":
    main()
