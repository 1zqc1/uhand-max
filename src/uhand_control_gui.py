#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机械手控制界面 - Python GUI
功能：蓝牙连接、实时数据显示、机械手控制
"""

import serial
import serial.tools.list_ports
import struct
import threading
import time
from tkinter import *
from tkinter import ttk, messagebox


# ============== 蓝牙协议定义 ==============
FRAME_HEADER = 0x55
CMD_SERVO_MOVE = 0x03
CMD_ACTION_GROUP_RUN = 0x06
CMD_ACTION_GROUP_STOP = 0x07
CMD_ACTION_GROUP_SPEED = 0x0B
CMD_GET_BATTERY_VOLTAGE = 0x0F


class BlueProtocol:
    """蓝牙协议处理"""

    @staticmethod
    def calc_checksum(data: bytes) -> int:
        return sum(data) & 0xFF

    @staticmethod
    def build_servo_move(servos: list) -> bytes:
        """构建舵机移动指令
        servos: [(id, position), ...] position范围 0-180
        """
        if not servos:
            return b''

        num = len(servos)
        time = 1000  # 默认时间 1000ms

        # 构建数据部分
        data = bytes([num]) + struct.pack('<H', time)
        for servo_id, pos in servos:
            data += bytes([servo_id, pos])

        # 添加帧头和命令
        frame = bytes([FRAME_HEADER, CMD_SERVO_MOVE]) + data
        checksum = BlueProtocol.calc_checksum(data)
        frame += bytes([checksum])

        return frame

    @staticmethod
    def build_action_group_run(group_num: int) -> bytes:
        data = bytes([group_num])
        frame = bytes([FRAME_HEADER, CMD_ACTION_GROUP_RUN]) + data
        checksum = BlueProtocol.calc_checksum(data)
        return frame + bytes([checksum])

    @staticmethod
    def build_action_group_stop() -> bytes:
        frame = bytes([FRAME_HEADER, CMD_ACTION_GROUP_STOP])
        return frame + bytes([CMD_ACTION_GROUP_STOP])

    @staticmethod
    def build_action_group_speed(speed: int) -> bytes:
        data = bytes([speed & 0xFF])
        frame = bytes([FRAME_HEADER, CMD_ACTION_GROUP_SPEED]) + data
        checksum = BlueProtocol.calc_checksum(data)
        return frame + bytes([checksum])

    @staticmethod
    def build_get_battery() -> bytes:
        return bytes([FRAME_HEADER, CMD_GET_BATTERY_VOLTAGE, CMD_GET_BATTERY_VOLTAGE])


class UhandControlGUI:
    """机械手控制界面主类"""

    def __init__(self):
        self.root = Tk()
        self.root.title("机械手控制界面")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        self.serial_port = None
        self.is_connected = False
        self.is_receiving = False
        self.receive_thread = None

        # 传感器数据
        self.sensor_data = {
            'pitch': 0.0,
            'roll': 0.0,
            'yaw': 0.0,
            'ultrasonic': 0,
            'battery': 0.0,
        }

        # 舵机角度
        self.servo_angles = [90, 90, 90, 90, 90, 90]

        self._setup_ui()

    def _setup_ui(self):
        """构建界面"""
        # 标题
        title_frame = Frame(self.root, bg="#2c3e50", height=50)
        title_frame.pack(fill=X)
        title_frame.pack_propagate(False)

        Label(
            title_frame,
            text="机械手控制中心",
            font=("微软雅黑", 18, "bold"),
            fg="white",
            bg="#2c3e50"
        ).pack(pady=10)

        # 主容器
        main_frame = Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=BOTH, expand=True)

        # 左侧控制面板
        left_frame = Frame(main_frame)
        left_frame.pack(side=LEFT, fill=Y, padx=(0, 10))

        # 右侧数据显示
        right_frame = Frame(main_frame)
        right_frame.pack(side=RIGHT, fill=BOTH, expand=True)

        self._setup_connection_panel(left_frame)
        self._setup_servo_panel(left_frame)
        self._setup_action_panel(left_frame)
        self._setup_sensor_panel(right_frame)

    def _setup_connection_panel(self, parent):
        """连接控制面板"""
        frame = LabelFrame(parent, text="连接控制", font=("微软雅黑", 12), padx=10, pady=10)
        frame.pack(fill=X, pady=(0, 10))

        # 串口选择
        Frame(frame).pack()  # 间距
        Label(frame, text="串口:").pack(anchor=W)
        self.port_var = StringVar()
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=15, state="readonly")
        self.port_combo.pack(fill=X, pady=(0, 5))
        self._refresh_ports()

        # 按钮行
        btn_frame = Frame(frame)
        btn_frame.pack(fill=X)
        Button(btn_frame, text="刷新", command=self._refresh_ports, width=8).pack(side=LEFT, padx=(0, 5))
        Button(btn_frame, text="连接", command=self._connect, bg="#27ae60", fg="white", width=8).pack(side=LEFT, padx=(0, 5))
        Button(btn_frame, text="断开", command=self._disconnect, bg="#e74c3c", fg="white", width=8).pack(side=LEFT)

        # 连接状态
        self.status_label = Label(frame, text="未连接", fg="red", font=("微软雅黑", 10))
        self.status_label.pack(anchor=W, pady=(5, 0))

        # 波特率
        Label(frame, text="波特率: 9600").pack(anchor=W)

    def _setup_servo_panel(self, parent):
        """舵机控制面板"""
        frame = LabelFrame(parent, text="舵机控制", font=("微软雅黑", 12), padx=10, pady=10)
        frame.pack(fill=X, pady=(0, 10))

        self.servo_vars = []
        self.servo_scales = []
        self.servo_labels = []

        servo_names = ["底座", "大臂", "小臂", "手腕", "食指", "拇指"]

        for i, name in enumerate(servo_names):
            row = Frame(frame)
            row.pack(fill=X, pady=2)

            Label(row, text=f"{name}:", width=6, anchor=W).pack(side=LEFT)

            var = IntVar(value=90)
            self.servo_vars.append(var)

            scale = Scale(
                row,
                from_=0,
                to=180,
                orient=HORIZONTAL,
                variable=var,
                showvalue=True,
                width=8,
                command=lambda v, idx=i: self._on_servo_change(idx)
            )
            scale.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
            self.servo_scales.append(scale)

            lbl = Label(row, text="90°", width=5)
            lbl.pack(side=RIGHT)
            self.servo_labels.append(lbl)

        # 应用按钮
        Button(
            frame,
            text="应用角度",
            command=self._apply_servo_angles,
            bg="#3498db",
            fg="white",
            font=("微软雅黑", 10)
        ).pack(fill=X, pady=(10, 0))

    def _setup_action_panel(self, parent):
        """动作组控制面板"""
        frame = LabelFrame(parent, text="动作组", font=("微软雅黑", 12), padx=10, pady=10)
        frame.pack(fill=X, pady=(0, 10))

        actions = [
            ("初始化(张开)", 0),
            ("握拳", 1),
            ("夹取", 2),
        ]

        for text, num in actions:
            Button(
                frame,
                text=text,
                command=lambda n=num: self._run_action(n),
                width=15
            ).pack(fill=X, pady=2)

        Button(
            frame,
            text="停止动作",
            command=self._stop_action,
            bg="#e74c3c",
            fg="white",
            width=15
        ).pack(fill=X, pady=(10, 0))

    def _setup_sensor_panel(self, parent):
        """传感器数据显示面板"""
        frame = LabelFrame(parent, text="实时数据", font=("微软雅黑", 12), padx=10, pady=10)
        frame.pack(fill=BOTH, expand=True)

        # 姿态数据
        attitude_frame = LabelFrame(frame, text="MPU6050 姿态角度", font=("微软雅黑", 10))
        attitude_frame.pack(fill=X, pady=(0, 10))

        self.pitch_var = StringVar(value="0.0°")
        self.roll_var = StringVar(value="0.0°")
        self.yaw_var = StringVar(value="0.0°")

        self._add_sensor_row(attitude_frame, "Pitch:", self.pitch_var).pack(fill=X, pady=2)
        self._add_sensor_row(attitude_frame, "Roll:", self.roll_var).pack(fill=X, pady=2)
        self._add_sensor_row(attitude_frame, "Yaw:", self.yaw_var).pack(fill=X, pady=2)

        # 超声波数据
        ultrasonic_frame = LabelFrame(frame, text="超声波距离", font=("微软雅黑", 10))
        ultrasonic_frame.pack(fill=X, pady=(0, 10))

        self.ultrasonic_var = StringVar(value="-- mm")
        row = Frame(ultrasonic_frame)
        row.pack(fill=X, pady=5)
        Label(row, text="距离:", width=10, anchor=W).pack(side=LEFT)
        Label(row, textvariable=self.ultrasonic_var, font=("微软雅黑", 14, "bold"), fg="#2980b9").pack(side=LEFT)

        # 电池数据
        battery_frame = LabelFrame(frame, text="电池状态", font=("微软雅黑", 10))
        battery_frame.pack(fill=X, pady=(0, 10))

        self.battery_var = StringVar(value="-- V")
        self.battery_pbar = ttk.Progressbar(battery_frame, length=200, mode='determinate')
        self.battery_pbar.pack(fill=X, pady=5)
        row = Frame(battery_frame)
        row.pack(fill=X)
        Label(row, text="电压:", width=10, anchor=W).pack(side=LEFT)
        Label(row, textvariable=self.battery_var, font=("微软雅黑", 12)).pack(side=LEFT)

        # 日志
        log_frame = LabelFrame(frame, text="通信日志", font=("微软雅黑", 10))
        log_frame.pack(fill=BOTH, expand=True)

        self.log_text = Text(log_frame, height=15, width=40, state=DISABLED, font=("Consolas", 9))
        self.log_text.pack(fill=BOTH, expand=True, pady=5)

        scrollbar = Scrollbar(self.log_text)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)

    def _add_sensor_row(self, parent, label_text, var):
        row = Frame(parent)
        Label(row, text=label_text, width=10, anchor=W).pack(side=LEFT)
        Label(row, textvariable=var, font=("微软雅黑", 12, "bold"), fg="#2980b9").pack(side=LEFT)
        return row

    def _refresh_ports(self):
        """刷新串口列表"""
        ports = list(serial.tools.list_ports.comports())
        port_list = [p.device for p in ports]
        self.port_combo['values'] = port_list
        if port_list:
            self.port_combo.current(0)

    def _connect(self):
        """连接串口"""
        port = self.port_var.get()
        if not port:
            messagebox.showwarning("警告", "请选择串口")
            return

        try:
            self.serial_port = serial.Serial(port, 9600, timeout=1)
            self.is_connected = True
            self.status_label.config(text=f"已连接: {port}", fg="green")

            # 启动接收线程
            self.is_receiving = True
            self.receive_thread = threading.Thread(target=self._receive_data, daemon=True)
            self.receive_thread.start()

            # 启动数据更新定时器
            self._update_loop()

            self._log(f"连接成功: {port}")
        except Exception as e:
            messagebox.showerror("错误", f"连接失败: {e}")

    def _disconnect(self):
        """断开连接"""
        self.is_receiving = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self.status_label.config(text="未连接", fg="red")
        self._log("连接已断开")

    def _receive_data(self):
        """接收数据线程"""
        buffer = bytearray()

        while self.is_receiving and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    buffer.extend(data)

                    # 解析数据
                    self._parse_data(buffer)
            except Exception as e:
                self._log(f"接收错误: {e}")
                break

    def _parse_data(self, buffer: bytearray):
        """解析接收到的数据"""
        while len(buffer) >= 3:
            # 查找帧头
            if buffer[0] != FRAME_HEADER:
                buffer.pop(0)
                continue

            cmd = buffer[1]

            if cmd == CMD_GET_BATTERY_VOLTAGE:
                if len(buffer) >= 4:
                    voltage = buffer[2] / 10.0
                    self.sensor_data['battery'] = voltage
                    buffer = buffer[4:]

            elif cmd == CMD_ACTION_GROUP_RUN:
                if len(buffer) >= 3:
                    buffer = buffer[3:]

            elif cmd == 0x55:  # 可能是姿态数据帧
                # 简化解析
                if len(buffer) >= 20:
                    try:
                        # 假设数据格式: 0x55, pitch, roll, yaw (float)
                        if len(buffer) >= 15:
                            import struct
                            data = bytes(buffer[2:14])
                            if len(data) >= 12:
                                pitch, roll, yaw = struct.unpack('<fff', data)
                                self.sensor_data['pitch'] = pitch
                                self.sensor_data['roll'] = roll
                                self.sensor_data['yaw'] = yaw
                    except:
                        pass
                    buffer = buffer[1:]

            else:
                buffer.pop(0)

    def _update_loop(self):
        """定时更新界面数据"""
        if not self.is_connected:
            return

        # 更新传感器显示
        self.pitch_var.set(f"{self.sensor_data['pitch']:.1f}°")
        self.roll_var.set(f"{self.sensor_data['roll']:.1f}°")
        self.yaw_var.set(f"{self.sensor_data['yaw']:.1f}°")
        self.ultrasonic_var.set(f"{self.sensor_data['ultrasonic']} mm")

        if self.sensor_data['battery'] > 0:
            self.battery_var.set(f"{self.sensor_data['battery']:.1f} V")
            # 假设满电8.4V
            pct = min(100, (self.sensor_data['battery'] / 8.4) * 100)
            self.battery_pbar['value'] = pct

        # 更新舵机标签
        for i, var in enumerate(self.servo_vars):
            self.servo_labels[i].config(text=f"{var.get()}°")

        # 定时发送查询指令
        if self.serial_port and self.serial_port.is_open:
            try:
                # 查询电池
                self.serial_port.write(BlueProtocol.build_get_battery())
            except:
                pass

        # 继续定时更新
        if self.is_connected:
            self.root.after(100, self._update_loop)

    def _on_servo_change(self, index):
        """舵机滑块变化"""
        pass  # 实时更新标签在_update_loop中处理

    def _apply_servo_angles(self):
        """应用舵机角度"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接")
            return

        servos = [(i + 1, self.servo_vars[i].get()) for i in range(6)]
        cmd = BlueProtocol.build_servo_move(servos)

        try:
            self.serial_port.write(cmd)
            self._log(f"发送舵机指令: {[s[1] for s in servos]}")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _run_action(self, action_num):
        """运行动作组"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接")
            return

        cmd = BlueProtocol.build_action_group_run(action_num)
        try:
            self.serial_port.write(cmd)
            self._log(f"运行动作组 {action_num}")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _stop_action(self):
        """停止动作"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接")
            return

        cmd = BlueProtocol.build_action_group_stop()
        try:
            self.serial_port.write(cmd)
            self._log("停止动作")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _log(self, message: str):
        """添加日志"""
        self.log_text.config(state=NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

    def run(self):
        """运行界面"""
        self.root.mainloop()


if __name__ == "__main__":
    app = UhandControlGUI()
    app.run()
