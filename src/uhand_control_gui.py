#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机械手控制界面
功能：串口控制机械手张开/闭合，实时显示超声波距离
"""

import serial
import serial.tools.list_ports
import threading
import time
from tkinter import *
from tkinter import ttk, messagebox


class UhandControlGUI:
    """机械手控制界面主类"""

    def __init__(self):
        self.root = Tk()
        self.root.title("机械手控制界面")
        self.root.geometry("400x550")
        self.root.resizable(True, True)
        self.root.configure(bg="#f5f5f5")

        self.serial_port = None
        self.is_connected = False
        self.is_receiving = False
        self.receive_thread = None

        # 传感器数据
        self.distance = 0
        self.mode = "未知"
        self.is_auto_mode = True  # 默认自动模式

        self._setup_ui()

    def _setup_ui(self):
        """构建界面"""

        # ============== 顶部标题 ==============
        title_frame = Frame(self.root, bg="#3498db", height=60)
        title_frame.pack(fill=X)
        title_frame.pack_propagate(False)

        Label(
            title_frame,
            text="机械手控制中心",
            font=("微软雅黑", 20, "bold"),
            fg="white",
            bg="#3498db"
        ).pack(pady=15)

        # ============== 数据显示区 ==============
        data_frame = LabelFrame(
            self.root,
            text="实时传感器数据",
            font=("微软雅黑", 12, "bold"),
            padx=15,
            pady=15,
            bg="#f5f5f5"
        )
        data_frame.pack(fill=X, padx=20, pady=(20, 10))

        # 超声波距离
        distance_box = Frame(data_frame, bg="#ecf0f1", relief=RIDGE, bd=2, width=150, height=80)
        distance_box.pack(pady=5)
        distance_box.pack_propagate(False)

        Label(
            distance_box,
            text="超声波距离",
            font=("微软雅黑", 10),
            bg="#ecf0f1",
            fg="#7f8c8d"
        ).pack(pady=(10, 2))

        self.distance_var = StringVar(value="-- mm")
        Label(
            distance_box,
            textvariable=self.distance_var,
            font=("微软雅黑", 28, "bold"),
            bg="#ecf0f1",
            fg="#2980b9"
        ).pack(pady=(0, 10))

        # 控制模式
        mode_box = Frame(data_frame, bg="#ecf0f1", relief=RIDGE, bd=2, width=150, height=80)
        mode_box.pack(pady=5)
        mode_box.pack_propagate(False)

        Label(
            mode_box,
            text="控制模式",
            font=("微软雅黑", 10),
            bg="#ecf0f1",
            fg="#7f8c8d"
        ).pack(pady=(10, 2))

        self.mode_var = StringVar(value="未知")
        self.mode_label = Label(
            mode_box,
            textvariable=self.mode_var,
            font=("微软雅黑", 20, "bold"),
            bg="#ecf0f1",
            fg="#27ae60"
        )
        self.mode_label.pack(pady=(0, 10))

        # ============== 串口连接区 ==============
        conn_frame = LabelFrame(
            self.root,
            text="串口连接",
            font=("微软雅黑", 12, "bold"),
            padx=15,
            pady=10,
            bg="#f5f5f5"
        )
        conn_frame.pack(fill=X, padx=20, pady=10)

        conn_inner = Frame(conn_frame, bg="#f5f5f5")
        conn_inner.pack()

        Label(conn_inner, text="串口:", font=("微软雅黑", 10), bg="#f5f5f5").pack(side=LEFT, padx=(0, 5))

        self.port_var = StringVar()
        self.port_combo = ttk.Combobox(conn_inner, textvariable=self.port_var, width=12, state="readonly")
        self.port_combo.pack(side=LEFT, padx=(0, 10))
        self._refresh_ports()

        Button(
            conn_inner,
            text="刷新",
            command=self._refresh_ports,
            width=6,
            bg="#95a5a6",
            fg="white"
        ).pack(side=LEFT, padx=2)

        Button(
            conn_inner,
            text="连接",
            command=self._connect,
            width=6,
            bg="#27ae60",
            fg="white"
        ).pack(side=LEFT, padx=2)

        Button(
            conn_inner,
            text="断开",
            command=self._disconnect,
            width=6,
            bg="#e74c3c",
            fg="white"
        ).pack(side=LEFT, padx=2)

        self.status_label = Label(
            conn_inner,
            text="未连接",
            fg="#e74c3c",
            font=("微软雅黑", 10, "bold"),
            bg="#f5f5f5"
        )
        self.status_label.pack(side=LEFT, padx=10)

        # ============== 模式切换区 ==============
        mode_switch_frame = LabelFrame(
            self.root,
            text="控制模式切换",
            font=("微软雅黑", 12, "bold"),
            padx=15,
            pady=10,
            bg="#f5f5f5"
        )
        mode_switch_frame.pack(fill=X, padx=20, pady=10)

        # 自动/手动模式切换说明
        mode_note = Label(
            mode_switch_frame,
            text="提示：默认自动模式，手动模式需要切换",
            font=("微软雅黑", 9),
            bg="#f5f5f5",
            fg="#7f8c8d"
        )
        mode_note.pack(pady=(0, 5))

        mode_btn_inner = Frame(mode_switch_frame, bg="#f5f5f5")
        mode_btn_inner.pack()

        # 切换到自动模式按钮
        self.auto_btn = Button(
            mode_btn_inner,
            text="自动模式",
            command=self._set_auto_mode,
            width=10,
            height=2,
            font=("微软雅黑", 11, "bold"),
            bg="#3498db",
            fg="white",
            activebackground="#2980b9",
            activeforeground="white",
            relief=RAISED,
            bd=3
        )
        self.auto_btn.pack(side=LEFT, padx=5)

        # 切换到手动模式按钮
        self.manual_btn = Button(
            mode_btn_inner,
            text="手动模式",
            command=self._set_manual_mode,
            width=10,
            height=2,
            font=("微软雅黑", 11, "bold"),
            bg="#9b59b6",
            fg="white",
            activebackground="#8e44ad",
            activeforeground="white",
            relief=RAISED,
            bd=3
        )
        self.manual_btn.pack(side=LEFT, padx=5)

        # 当前模式状态指示
        self.mode_indicator = Label(
            mode_switch_frame,
            text="当前: 自动模式",
            font=("微软雅黑", 10, "bold"),
            bg="#f5f5f5",
            fg="#3498db"
        )
        self.mode_indicator.pack(pady=(5, 0))

        # ============== 手掌控制区（手动模式） ==============
        gripper_frame = LabelFrame(
            self.root,
            text="手掌控制（手动模式）",
            font=("微软雅黑", 12, "bold"),
            padx=20,
            pady=15,
            bg="#f5f5f5"
        )
        gripper_frame.pack(fill=X, padx=20, pady=10)

        gripper_inner = Frame(gripper_frame, bg="#f5f5f5")
        gripper_inner.pack()

        # 张开按钮
        self.open_btn = Button(
            gripper_inner,
            text="张开(O)",
            command=self._gripper_open,
            width=8,
            height=2,
            font=("微软雅黑", 12, "bold"),
            bg="#2ecc71",
            fg="white",
            activebackground="#27ae60",
            activeforeground="white",
            relief=RAISED,
            bd=3,
            state=DISABLED
        )
        self.open_btn.pack(side=LEFT, padx=5, pady=3)

        # 闭合按钮
        self.close_btn = Button(
            gripper_inner,
            text="闭合(C)",
            command=self._gripper_close,
            width=8,
            height=2,
            font=("微软雅黑", 12, "bold"),
            bg="#e74c3c",
            fg="white",
            activebackground="#c0392b",
            activeforeground="white",
            relief=RAISED,
            bd=3,
            state=DISABLED
        )
        self.close_btn.pack(side=LEFT, padx=5, pady=3)

        # 握手按钮
        self.handshake_btn = Button(
            gripper_inner,
            text="握手(H)",
            command=self._gripper_handshake,
            width=8,
            height=2,
            font=("微软雅黑", 12, "bold"),
            bg="#3498db",
            fg="white",
            activebackground="#2980b9",
            activeforeground="white",
            relief=RAISED,
            bd=3,
            state=DISABLED
        )
        self.handshake_btn.pack(side=LEFT, padx=5, pady=3)

        # 捏取按钮
        self.pinch_btn = Button(
            gripper_inner,
            text="捏取(P)",
            command=self._gripper_pinch,
            width=8,
            height=2,
            font=("微软雅黑", 12, "bold"),
            bg="#9b59b6",
            fg="white",
            activebackground="#8e44ad",
            activeforeground="white",
            relief=RAISED,
            bd=3,
            state=DISABLED
        )
        self.pinch_btn.pack(side=LEFT, padx=5, pady=3)

        # 全握按钮
        self.grip_btn = Button(
            gripper_inner,
            text="全握(G)",
            command=self._gripper_grip,
            width=8,
            height=2,
            font=("微软雅黑", 12, "bold"),
            bg="#e67e22",
            fg="white",
            activebackground="#d35400",
            activeforeground="white",
            relief=RAISED,
            bd=3,
            state=DISABLED
        )
        self.grip_btn.pack(side=LEFT, padx=5, pady=3)

        # 指向按钮
        self.point_btn = Button(
            gripper_inner,
            text="指向(F)",
            command=self._gripper_point,
            width=8,
            height=2,
            font=("微软雅黑", 12, "bold"),
            bg="#1abc9c",
            fg="white",
            activebackground="#16a085",
            activeforeground="white",
            relief=RAISED,
            bd=3,
            state=DISABLED
        )
        self.point_btn.pack(side=LEFT, padx=5, pady=3)

        # 放松按钮
        self.relax_btn = Button(
            gripper_inner,
            text="放松(R)",
            command=self._gripper_relax,
            width=8,
            height=2,
            font=("微软雅黑", 12, "bold"),
            bg="#95a5a6",
            fg="white",
            activebackground="#7f8c8d",
            activeforeground="white",
            relief=RAISED,
            bd=3,
            state=DISABLED
        )
        self.relax_btn.pack(side=LEFT, padx=5, pady=3)

        # 状态提示
        self.gripper_status = StringVar(value="状态: 请先连接")
        Label(
            gripper_frame,
            textvariable=self.gripper_status,
            font=("微软雅黑", 12),
            bg="#f5f5f5",
            fg="#7f8c8d"
        ).pack(pady=(5, 0))

        # ============== 日志区 ==============
        log_frame = LabelFrame(
            self.root,
            text="通信日志",
            font=("微软雅黑", 11),
            padx=10,
            pady=5,
            bg="#f5f5f5"
        )
        log_frame.pack(fill=BOTH, expand=True, padx=20, pady=(10, 20))

        self.log_text = Text(log_frame, height=6, width=45, state=DISABLED, font=("Consolas", 9))
        self.log_text.pack(fill=BOTH, expand=True, pady=5)

        scrollbar = Scrollbar(self.log_text)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)

    def _refresh_ports(self):
        """刷新串口列表"""
        ports = list(serial.tools.list_ports.comports())
        port_list = [p.device for p in ports]
        self.port_combo['values'] = port_list
        if port_list:
            self.port_combo.current(0)

    def _set_buttons_state(self, state):
        """设置按钮状态"""
        self.open_btn.config(state=state)
        self.close_btn.config(state=state)
        self.handshake_btn.config(state=state)
        self.pinch_btn.config(state=state)
        self.grip_btn.config(state=state)
        self.point_btn.config(state=state)
        self.relax_btn.config(state=state)
        self.auto_btn.config(state=state)
        self.manual_btn.config(state=state)

    def _update_mode_display(self):
        """更新模式显示"""
        if self.is_auto_mode:
            self.mode_indicator.config(text="当前: 自动模式", fg="#3498db")
            self.mode_var.set("自动")
            # 自动模式下禁用手动控制按钮
            self._set_buttons_state(DISABLED)
            self.gripper_status.set("状态: 自动跟随距离")
        else:
            self.mode_indicator.config(text="当前: 手动模式", fg="#9b59b6")
            # 手动模式下启用所有控制按钮
            self._set_buttons_state(NORMAL)
            self.gripper_status.set("状态: 手动控制")

    def _connect(self):
        """连接串口"""
        port = self.port_var.get()
        if not port:
            messagebox.showwarning("警告", "请选择串口")
            return

        try:
            self.serial_port = serial.Serial(port, 9600, timeout=0.5)
            self.is_connected = True
            self.is_receiving = True
            self.status_label.config(text="已连接", fg="#27ae60")

            # 启用所有按钮
            self._set_buttons_state(NORMAL)

            # 默认自动模式
            self.is_auto_mode = True
            self._update_mode_display()

            self.receive_thread = threading.Thread(target=self._receive_data, daemon=True)
            self.receive_thread.start()

            self._update_loop()
            self._log(f"连接成功: {port}")
            self.gripper_status.set("状态: 就绪")
        except Exception as e:
            messagebox.showerror("错误", f"连接失败: {e}")

    def _disconnect(self):
        """断开连接"""
        self.is_receiving = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self.status_label.config(text="未连接", fg="#e74c3c")
        self.gripper_status.set("状态: 请先连接")
        self.mode_var.set("未知")
        self.distance_var.set("-- mm")
        self.mode_indicator.config(text="当前: 未连接", fg="#7f8c8d")

        # 禁用所有按钮
        self._set_buttons_state(DISABLED)
        self._log("连接已断开")

    def _receive_data(self):
        """接收数据线程"""
        buffer = ""

        while self.is_receiving and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data

                    # 处理完整行
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self._parse_line(line)
            except Exception as e:
                self._log(f"接收错误: {e}")
                break

    def _parse_line(self, line: str):
        """解析数据行"""
        # DIST:xxx - 距离数据
        if line.startswith("DIST:"):
            try:
                self.distance = int(line[5:])
            except ValueError:
                pass
        # MODE:1-9 - 模式数据
        elif line.startswith("MODE:"):
            mode_num = line[5:]
            mode_map = {
                "1": "张开", "2": "闭合", "3": "自动",
                "4": "握手", "5": "捏取", "6": "全握",
                "7": "指向", "8": "放松", "9": "手动"
            }
            mode = mode_map.get(mode_num, "未知")
            self.mode = mode
            # 根据Arduino返回的模式更新GUI状态
            if mode_num == "3":
                self.is_auto_mode = True
            else:
                self.is_auto_mode = False
        # CMD:xxx - 命令确认
        elif line.startswith("CMD:"):
            cmd_raw = line[4:].strip()
            cmd_map = {
                "OPEN": "张开", "CLOSE": "闭合", "AUTO": "自动",
                "MANUAL": "手动", "HANDSHAKE": "握手", "PINCH": "捏取",
                "GRIP": "全握", "POINT": "指向", "RELAX": "放松",
                "QUERY": "查询"
            }
            cmd = cmd_map.get(cmd_raw, cmd_raw)
            self.mode = cmd
            if cmd == "自动":
                self.is_auto_mode = True
            else:
                self.is_auto_mode = False

    def _update_loop(self):
        """定时更新界面数据"""
        if not self.is_connected:
            return

        # 更新距离显示
        if self.distance > 0:
            self.distance_var.set(f"{self.distance} mm")
        else:
            self.distance_var.set("-- mm")

        # 更新模式显示
        self._update_mode_display()

        # 发送查询命令获取距离
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(b'?')
            except:
                pass

        if self.is_connected:
            self.root.after(200, self._update_loop)

    def _set_auto_mode(self):
        """切换到自动模式"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        try:
            self.serial_port.write(b'A')
            self.is_auto_mode = True
            self._update_mode_display()
            self._log("切换到自动模式")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _set_manual_mode(self):
        """切换到手动模式"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        try:
            self.serial_port.write(b'M')  # M = Manual，手动模式，初始化为张开
            self.is_auto_mode = False
            self._update_mode_display()
            self._log("切换到手动模式")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _gripper_open(self):
        """张开手掌"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        try:
            self.serial_port.write(b'O')
            self.gripper_status.set("状态: 张开")
            self._log("发送命令: 张开")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _gripper_close(self):
        """闭合手掌"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        try:
            self.serial_port.write(b'C')
            self.gripper_status.set("状态: 闭合")
            self._log("发送命令: 闭合")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _gripper_handshake(self):
        """握手模式"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        try:
            self.serial_port.write(b'H')
            self.gripper_status.set("状态: 握手")
            self._log("发送命令: 握手")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _gripper_pinch(self):
        """捏取模式"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        try:
            self.serial_port.write(b'P')
            self.gripper_status.set("状态: 捏取")
            self._log("发送命令: 捏取")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _gripper_grip(self):
        """全握模式"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        try:
            self.serial_port.write(b'G')
            self.gripper_status.set("状态: 全握")
            self._log("发送命令: 全握")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _gripper_point(self):
        """指向模式"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        try:
            self.serial_port.write(b'F')
            self.gripper_status.set("状态: 指向")
            self._log("发送命令: 指向")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _gripper_relax(self):
        """放松模式"""
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return

        try:
            self.serial_port.write(b'R')
            self.gripper_status.set("状态: 放松")
            self._log("发送命令: 放松")
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