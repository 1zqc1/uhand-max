# ESP32-CAM + YOLO 目标检测 - 详细步骤指南

> 本指南将一步一步教你在飞腾派上运行YOLO目标检测

---

## 第一阶段：在Windows PC上准备模型

### 步骤 1.1：下载 YOLOv5s 模型文件

**1.1.1** 打开Windows文件资源管理器

**1.1.2** 创建一个文件夹用于存放模型，例如：`D:\YOLOModels`

**1.1.3** 访问 GitHub 下载 YOLOv5s ONNX 模型：

- 打开浏览器访问：https://github.com/ultralytics/yolov5/releases/tag/v7.0
- 向下滚动找到 **Assets** 部分
- 找到 `yolov5s.onnx` 文件（约14MB）
- 点击下载

**或者** 直接双击下面的链接下载：
```
https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx
```

**1.1.4** 将下载的 `yolov5s.onnx` 文件移动到 `D:\YOLOModels` 文件夹

**1.1.5** 确认文件存在：`D:\YOLOModels\yolov5s.onnx`

---

### 步骤 1.2：安装 FinalShell 或使用 SCP 传输工具

我们需要一个工具将文件从Windows传输到飞腾派。

**推荐工具：FinalShell**

**1.2.1** 下载 FinalShell：
- 官网：http://www.hostbuf.com/
- 下载 Windows 版本

**1.2.2** 安装并打开 FinalShell

**1.2.3** 创建连接：
```
主机(H)：飞腾派的IP地址，例如 192.168.5.1
端口(P)：22
用户名：root（或你设置的用户名）
密码：你的密码
```

**1.2.4** 点击连接登录飞腾派

---

## 第二阶段：在飞腾派上准备工作

### 步骤 2.1：连接ESP32-CAM的WiFi热点

**2.1.1** 在飞腾派的桌面或命令行，连接ESP32-CAM的WiFi热点：
- SSID: `HW_ESP32S3CAM`（注意是ESP32-S3，不是普通ESP32-CAM）
- 密码: （无密码）
- 或者 SSID: `HW_ESP32Cam`（取决于你的模块型号）

**2.1.2** 验证连接：
```bash
# 在飞腾派终端执行
iwconfig
# 或
ip addr show wlan0
```

**2.1.3** 测试ESP32-CAM视频流是否可访问：
```bash
curl -I http://192.168.5.1:81/stream
```
如果返回 `HTTP/1.1 200 OK`，说明连接正常。

---

### 步骤 2.2：在飞腾派上创建项目目录

**2.2.1** 登录飞腾派（通过HDMI显示器+键盘，或FinalShell SSH）

**2.2.2** 创建存放模型的目录：
```bash
mkdir -p ~/uhand-max/models
```

**2.2.3** 确认目录存在：
```bash
ls -la ~/uhand-max/
```
你应该看到 `models` 文件夹。

---

### 步骤 2.3：传输模型文件到飞腾派

**方法一：使用 FinalShell（推荐）**

**2.3.1** 在FinalShell的左侧文件浏览器中

**2.3.2** 找到Windows上的 `D:\YOLOModels\yolov5s.onnx` 文件

**2.3.3** 直接拖拽到FinalShell左侧的 `/root/uhand-max/models/` 目录

**2.3.4** 等待传输完成（约14MB，可能需要1-2分钟）

**方法二：使用 SCP 命令**

**2.3.5** 打开Windows的PowerShell或命令提示符

**2.3.6** 执行以下命令：
```bash
# 确保Windows上已经安装好了SCP（大多数Windows 10/11自带）
scp D:\YOLOModels\yolov5s.onnx root@192.168.5.1:/root/uhand-max/models/
```

**2.3.7** 如果提示输入密码，输入飞腾派的root密码

**2.3.8** 等待传输完成

**2.3.9** 验证文件已传输：
```bash
ls -lh ~/uhand-max/models/
```
应该看到 `yolov5s.onnx` 文件。

---

### 步骤 2.4：更新代码仓库

**2.4.1** 在飞腾派上进入项目目录：
```bash
cd ~/uhand-max
```

**2.4.2** 拉取最新代码：
```bash
git pull origin master
```

**2.4.3** 确认文件存在：
```bash
ls -la src/ | grep yolo
```
应该看到 `esp32_cam_yolo.py` 文件。

---

## 第三阶段：运行YOLO检测程序

### 步骤 3.1：确保ESP32-CAM已启动并传输视频流

**3.1.1** 确认ESP32-CAM已上电并正常工作

**3.1.2** 确认手机或电脑可以访问 http://192.168.5.1:81/stream

**3.1.3** 如果无法访问，检查：
- ESP32-CAM的WiFi是否已连接
- IP地址是否为192.168.5.1
- 端口是否为81

---

### 步骤 3.2：运行YOLO检测程序

**3.2.1** 在飞腾派终端执行：
```bash
cd ~/uhand-max
python3 src/esp32_cam_yolo.py
```

**3.2.2** 如果一切正常，你应该看到：
```
==================================================
ESP32-CAM + YOLO 目标检测
==================================================
视频流: http://192.168.5.1:81/stream
模型: models/yolov5s.onnx
==================================================
按键说明:
  q - 退出程序
  s - 截图
  f - 切换 FPS 显示
  d - 切换调试信息
==================================================
[INFO] 连接到: http://192.168.5.1:81/stream
[INFO] 连接成功，开始接收视频流
[SUCCESS] 视频流已连接
```

**3.2.3** 此时HDMI显示器上应该显示ESP32-CAM的视频画面，并带有YOLO检测框

---

### 步骤 3.3：如果程序无法运行

**问题1：提示 `Module not found`**

**3.3.1** 安装必要的Python包：
```bash
pip3 install numpy opencv-python
```

**问题2：提示 `No module named 'cv2'`**

**3.3.2** OpenCV安装可能有问题，尝试：
```bash
pip3 install opencv-python-headless
```

**问题3：提示 `ONNX model not found`**

**3.3.3** 检查模型文件是否存在：
```bash
ls -la ~/uhand-max/models/
```

**3.3.4** 如果文件不存在或为空，重新传输模型文件

**问题4：视频流连接失败**

**3.4.1** 检查WiFi连接：
```bash
iwconfig
ping 192.168.5.1
```

**3.4.2** 检查ESP32-CAM是否正常工作

---

## 第四阶段：验证和调试

### 步骤 4.1：功能验证

**4.1.1** 程序运行后，观察HDMI显示器

**4.1.2** 应该能看到实时视频画面

**4.1.3** 如果检测到目标（人、车等COCO数据集包含的物体），应该显示彩色框

**4.1.4** 按 `s` 键截图，截图保存在 `~/uhand-max/` 目录

---

### 步骤 4.2：快捷键说明

| 按键 | 功能 |
|------|------|
| `q` | 退出程序 |
| `s` | 截图保存 |
| `f` | 显示/隐藏 FPS |
| `d` | 显示/隐藏 调试信息 |

---

## 第五阶段：训练自定义模型（可选）

### 场景说明

如果COCO预训练模型中的类别不够用（比如你想检测"红色球"或"机械手"），需要训练自定义模型。

### 步骤 5.1：采集训练数据

**5.1.1** 在飞腾派上运行数据采集脚本：
```bash
python3 src/collect_images.py --ip 192.168.5.1 --output my_dataset --count 200
```

**5.1.2** 这会采集200张图片保存到 `my_dataset` 目录

**5.1.3** 将图片拷贝到Windows PC进行标注

### 步骤 5.2：标注数据（使用 LabelImg）

**5.2.1** 在Windows PC上安装 LabelImg：
```bash
pip install labelImg
```

**5.2.2** 启动标注工具：
```bash
labelImg
```

**5.2.3** 设置：
- 点击 "Open Dir" 打开图片目录
- 点击 "Change Save Dir" 设置标注文件保存目录
- 设置 PascalVOC 格式（保存为 XML）

**5.2.4** 为每张图片画框并选择类别

### 步骤 5.3：训练模型（在PC上进行）

**5.3.1** 在Windows PC上安装训练环境：
```bash
pip install torch torchvision ultralytics
```

**5.3.2** 创建训练脚本 `train.py`：
```python
from ultralytics import YOLO

# 加载预训练模型
model = YOLO('yolov8n.pt')

# 训练（使用你自己的数据集）
results = model.train(
    data='my_dataset.yaml',  # 数据集配置
    epochs=50,
    imgsz=320,
    batch=8
)

# 导出为ONNX
model.export(format='onnx')
```

**5.3.3** 将训练好的 `best.onnx` 拷贝到飞腾派：
```bash
scp best.onnx root@192.168.5.1:/root/uhand-max/models/
```

**5.3.4** 运行：
```bash
python3 src/esp32_cam_yolo.py 192.168.5.1 81 models/best.onnx
```

---

## 常见问题速查

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| 无法连接ESP32-CAM | WiFi未连接 | 连接正确的WiFi热点 |
| HTTP 404 | 端口错误 | 使用端口 81 |
| 显示但无检测框 | 模型未加载 | 检查ONNX文件是否存在 |
| 程序崩溃 | OpenCV问题 | `pip3 install opencv-python-headless` |
| 太卡顿 | CPU太慢 | 使用 tiny 模型或降低分辨率 |

---

## 下一步建议

1. **先运行起来** - 完成上面的步骤1-3
2. **优化效果** - 根据实际检测效果调整参数
3. **自定义模型** - 如果需要检测特定物体，参考步骤5

有问题随时问！
