# YOLO 自定义模型训练指南

## 环境准备

### 1. 安装 Python 依赖

```bash
# 在 PC 上执行（不是飞腾派）
pip install torch torchvision
pip install ultralytics  # YOLOv5/v8 官方库
pip install opencv-python
```

### 2. 验证 GPU 可用性（推荐使用 GPU 加速训练）

```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

---

## 方法一：使用 Ultralytics 训练 YOLOv8（推荐）

### 步骤 1：准备数据集

```
dataset/
├── images/
│   ├── train/
│   │   ├── image1.jpg
│   │   └── image2.jpg
│   └── val/
│       └── image3.jpg
├── labels/
│   ├── train/
│   │   ├── image1.txt  # 标注文件
│   │   └── image2.txt
│   └── val/
│       └── image3.txt
└── data.yaml
```

### 步骤 2：创建数据集配置文件 `data.yaml`

```yaml
# data.yaml
path: ./dataset          # 数据集根目录
train: images/train      # 训练集路径
val: images/val          # 验证集路径

# 类别数
nc: 3

# 类别名称
names:
  0: red_ball
  1: blue_box
  2: hand
```

### 步骤 3：标注格式

YOLO 格式：`class x_center y_center width height`
（所有值都是相对于图像宽高的比例，0-1之间）

```
# example.txt 内容：
0 0.5 0.5 0.2 0.2    # class_id=0, 中心(50%,50%), 宽20%, 高20%
1 0.3 0.4 0.1 0.15   # class_id=1
```

### 步骤 4：训练模型

```bash
from ultralytics import YOLO

# 加载预训练模型（推荐使用 yolov8n.pt 纳米版，速度最快）
model = YOLO('yolov8n.pt')

# 开始训练
results = model.train(
    data='data.yaml',      # 数据集配置
    epochs=100,            # 训练轮数
    imgsz=640,             # 输入图像大小
    batch=16,              # 批次大小（根据GPU内存调整）
    device=0,              # 使用 GPU，'-1' 表示 CPU
    project='runs/detect', # 输出目录
    name='hand_detect'     # 实验名称
)

# 导出为 ONNX 格式
model.export(format='onnx')
```

### 步骤 5：获取训练好的模型

```
runs/detect/hand_detect/weights/best.onnx
```

---

## 方法二：使用 Darknet 训练 YOLOv3/v4

### 步骤 1：安装 Darknet

```bash
git clone https://github.com/AlexeyAB/darknet.git
cd darknet
mkdir build_release
cd build_release
cmake ..
make -j$(nproc)
```

### 步骤 2：准备数据集

同上，标注格式相同

### 步骤 3：修改配置文件

创建 `yolov3-tiny-custom.cfg`：

```ini
[net]
batch=64
subdivisions=16
width=416
height=416
channels=3
momentum=0.9
decay=0.0005
...
max_batches = 6000  # (classes * 2000)
steps = 4800,5400   # (80%, 90% of max_batches)

[yolo]
classes=3   # 你的类别数
```

创建 `obj.names`：
```
red_ball
blue_box
hand
```

创建 `obj.data`：
```
classes = 3
train = train.txt
valid = val.txt
names = obj.names
backup = backup/
```

### 步骤 4：开始训练

```bash
./darknet detector train obj.data yolov3-tiny-custom.cfg darknet53.conv.74
```

### 步骤 5：转换为 ONNX

使用 `darknet2onnx` 工具转换

---

## 方法三：使用 Google Colab（免GPU）

如果PC没有强力GPU，可以使用Google Colab免费GPU：

1. 打开 https://colab.research.google.com
2. 上传数据集到 Google Drive
3. 执行训练代码

```python
# Colab 代码
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.train(data='/content/drive/MyDrive/dataset/data.yaml', epochs=100)
model.export(format='onnx')
```

---

## 快速开始：用已有数据集

### 收集 ESP32-CAM 图像

```bash
# 在飞腾派上运行，采集图像用于训练
python3 src/esp32_cam_capture.py --output dataset --count 100
```

### 推荐的数据集

| 数据集 | 用途 | 下载 |
|--------|------|------|
| COCO128 | 预训练验证 | 内置 |
| hand_dataset | 手势检测 | 自行采集 |
| ball_dataset | 球体检测 | 自行采集 |

---

## 常见问题

### Q: 训练时显存不足
```python
# 减小 batch size
batch=8  # 或 4
```

### Q: 模型太大，飞腾派跑不动
```python
# 使用纳米版模型
model = YOLO('yolov8n.pt')  # nano, 最小

# 或导出时指定输入大小
model.export(format='onnx', imgsz=320)
```

### Q: 检测效果不好
- 增加训练数据
- 增加 epochs
- 调整数据增强参数

---

## 输出模型

训练完成后，将 `.onnx` 文件复制到飞腾派：

```bash
# 在飞腾派上
scp best.onnx pi@192.168.x.x:/home/pi/uhand-max/models/
```

然后运行：
```bash
python3 src/esp32_cam_yolo.py 192.168.5.1 81 models/best.onnx
```
