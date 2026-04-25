#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机械手控制界面 - 黄金比例配色 + 卡片式布局
"""

import serial
import serial.tools.list_ports
import threading
import time
import math
from tkinter import *
from tkinter import ttk, messagebox


# ================= 黄金比例配色方案 =================
# 主色调 60% | 辅助色 30% | 点缀色 10%
COLORS = {
    "bg_main": "#1a1a2e",       # 主色调 - 深蓝
    "bg_card": "#242442",       # 卡片背景
    "accent": "#0066cc",        # 辅助色 - 蓝色
    "accent_light": "#3a8ad6",  # 浅辅助色
    "neon": "#00d9ff",         # 点缀色 - 霓虹蓝
    "neon_green": "#00ff88",   # 点缀色 - 霓虹绿
    "neon_orange": "#ff8800",   # 点缀色 - 橙色
    "text": "#e0e0e0",         # 文字色
    "text_dim": "#8899aa",     # 次要文字
    "shadow": "#0a0a1e",       # 阴影色（非纯黑）
    "danger": "#cc3355",        # 危险色
}


class GaugeCard(Canvas):
    """仪表盘卡片"""

    def __init__(self, parent, title, unit="mm", **kwargs):
        super().__init__(parent, **kwargs)
        self.title = title
        self.unit = unit
        self.value = 0
        self.max_value = 500

    def set_value(self, val):
        self.value = min(max(val, 0), self.max_value)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 40:
            return

        cx, cy, r = w / 2, h / 2 - 10, min(w, h) / 2 - 25

        # 背景圆弧
        self.create_arc(cx - r, cy - r, cx + r, cy + r,
                        start=135, extent=270, style=ARC,
                        outline=COLORS["shadow"], width=14)

        # 数值圆弧
        ratio = self.value / self.max_value
        ext = int(ratio * 270)
        if ext > 0:
            if self.value < 80:
                color = COLORS["neon_green"]
            elif self.value < 200:
                color = COLORS["neon"]
            else:
                color = COLORS["neon_orange"]
            self.create_arc(cx - r, cy - r, cx + r, cy + r,
                            start=135, extent=ext, style=ARC,
                            outline=color, width=12)

        # 中心数值
        self.create_text(cx, cy - 8, text=f"{self.value}",
                        fill=COLORS["neon"], font=("Arial", 22, "bold"))
        self.create_text(cx, cy + 18, text=self.unit,
                        fill=COLORS["text_dim"], font=("Arial", 9))

        # 刻度
        for i in range(5):
            angle = math.radians(135 + i * 67.5)
            x1 = cx + (r - 18) * math.cos(angle)
            y1 = cy + (r - 18) * math.sin(angle)
            x2 = cx + (r - 6) * math.cos(angle)
            y2 = cy + (r - 6) * math.sin(angle)
            self.create_line(x1, y1, x2, y2, fill=COLORS["accent"], width=2)


class TiltCard(Canvas):
    """云台倾斜卡片"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.angle = 0

    def set_angle(self, val):
        self.angle = val
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 40:
            return

        cx, cy, r = w / 2, h / 2 - 10, min(w, h) / 2 - 25

        # 背景圆
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                        outline=COLORS["shadow"], width=4)

        # 中心点
        self.create_oval(cx - 5, cy - 5, cx + 5, cy + 5,
                        fill=COLORS["accent"])

        # 指针
        rad = math.radians(90 - self.angle * 2)
        px = cx + (r - 20) * math.cos(rad)
        py = cy - (r - 20) * math.sin(rad)

        color = COLORS["neon_green"] if abs(self.angle) < 10 else COLORS["neon_orange"]
        self.create_line(cx, cy, px, py, fill=color, width=3)
        self.create_oval(px - 7, py - 7, px + 7, py + 7, fill=color)

        # 角度值
        self.create_text(cx, cy + r + 15, text=f"{self.angle:.1f}°",
                        fill=COLORS["neon"], font=("Arial", 12, "bold"))


class CollapsibleSection(Frame):
    """可折叠区域"""

    def __init__(self, parent, title, default_open=False, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)

        self.title = title
        self.is_open = default_open

        # 标题栏（可点击）
        self.header = Frame(self, bg=COLORS["accent"])
        self.header.pack(fill=X)

        self.header_label = Label(self.header,
                                 text=f"{'▼' if default_open else '▶'} {title}",
                                 font=("微软雅黑", 11, "bold"),
                                 fg="white", bg=COLORS["accent"], anchor=W,
                                 cursor="hand2")
        self.header_label.pack(side=LEFT, padx=15, pady=8)
        self.header_label.bind("<Button-1>", self._on_header_click)

        # 内容区
        self.content = Frame(self, bg=COLORS["bg_card"])
        if default_open:
            self.content.pack(fill=X, padx=10, pady=(0, 10))

    def _on_header_click(self, _event=None):
        """处理标题栏点击"""
        self.is_open = not self.is_open
        if self.is_open:
            self.content.pack(fill=X, padx=10, pady=(0, 10))
            self.header_label.config(text=f"▼ {self.title}")
        else:
            self.content.pack_forget()
            self.header_label.config(text=f"▶ {self.title}")

    def toggle(self):
        """手动切换（兼容外部调用）"""
        self._on_header_click()

    def get_content(self):
        return self.content


class UhandControlGUI:
    """机械手控制界面"""

    def __init__(self):
        self.root = Tk()
        self.root.title("uHand 智能机械手")
        self.root.geometry("800x650")
        self.root.configure(bg=COLORS["bg_main"])

        self.serial_port = None
        self.is_connected = False
        self.is_receiving = False
        self.receive_thread = None

        self.distance = 0
        self.angle = 0
        self.is_auto_mode = True

        self._setup_ui()

    def _setup_ui(self):
        """构建界面"""

        # ============== 标题栏 ==============
        header = Frame(self.root, bg=COLORS["accent"], height=45)
        header.pack(fill=X)
        header.pack_propagate(False)

        Label(header, text="uHand 智能机械手控制中心",
              font=("微软雅黑", 16, "bold"), fg="white",
              bg=COLORS["accent"]).pack(side=LEFT, padx=20, pady=8)

        self.status_led = Label(header, text="●", font=("Arial", 16),
                              fg=COLORS["danger"], bg=COLORS["accent"])
        self.status_led.pack(side=RIGHT, padx=20)

        # ============== 主内容区 ==============
        main = Frame(self.root, bg=COLORS["bg_main"])
        main.pack(fill=BOTH, expand=True, padx=20, pady=15)

        # -------- 第一行：仪表盘（60%宽度）--------
        gauge_row = Frame(main, bg=COLORS["bg_main"])
        gauge_row.pack(fill=X, pady=(0, 15))

        # 超声波仪表
        gauge_card = Frame(gauge_row, bg=COLORS["bg_card"], bd=0)
        gauge_card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

        Label(gauge_card, text="超声波距离",
              font=("微软雅黑", 11, "bold"),
              fg=COLORS["neon"], bg=COLORS["bg_card"]).pack(pady=(12, 5))

        self.gauge = GaugeCard(gauge_card, "超声波", unit="mm",
                              width=220, height=170, bg=COLORS["bg_card"])
        self.gauge.pack(pady=5)

        # 云台仪表
        tilt_card = Frame(gauge_row, bg=COLORS["bg_card"], bd=0)
        tilt_card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

        Label(tilt_card, text="云台角度",
              font=("微软雅黑", 11, "bold"),
              fg=COLORS["neon"], bg=COLORS["bg_card"]).pack(pady=(12, 5))

        self.tilt = TiltCard(tilt_card, width=200, height=170, bg=COLORS["bg_card"])
        self.tilt.pack(pady=5)

        # 状态卡片
        status_card = Frame(gauge_row, bg=COLORS["bg_card"], bd=0)
        status_card.pack(side=LEFT, fill=Y, padx=(0, 10))

        Label(status_card, text="连接状态",
              font=("微软雅黑", 11, "bold"),
              fg=COLORS["neon"], bg=COLORS["bg_card"]).pack(pady=(12, 5))

        status_inner = Frame(status_card, bg=COLORS["bg_card"])
        status_inner.pack(padx=15, pady=5)

        self.conn_label = Label(status_inner, text="未连接",
                              font=("微软雅黑", 12, "bold"),
                              fg=COLORS["danger"], bg=COLORS["bg_card"],
                              anchor=W, width=12)
        self.conn_label.pack(pady=3)

        self.mode_label = Label(status_inner, text="模式: 自动",
                              font=("微软雅黑", 11),
                              fg=COLORS["text_dim"], bg=COLORS["bg_card"],
                              anchor=W, width=12)
        self.mode_label.pack(pady=3)

        self.status_label = Label(status_inner, text="状态: 就绪",
                              font=("微软雅黑", 10),
                              fg=COLORS["text_dim"], bg=COLORS["bg_card"],
                              anchor=W, width=12)
        self.status_label.pack(pady=3)

        # 连接控制
        conn_ctrl = Frame(status_card, bg=COLORS["bg_card"])
        conn_ctrl.pack(pady=10, padx=15)

        self.port_combo = ttk.Combobox(conn_ctrl, width=10, state="readonly")
        self.port_combo.pack(side=LEFT, padx=(0, 5))
        self._refresh_ports()

        Button(conn_ctrl, text="连接", command=self._connect,
               width=5, bg="#006633", fg="white",
               relief=FLAT, cursor="hand2").pack(side=LEFT, padx=2)
        Button(conn_ctrl, text="断开", command=self._disconnect,
               width=5, bg="#660033", fg="white",
               relief=FLAT, cursor="hand2").pack(side=LEFT, padx=2)
        Button(conn_ctrl, text="刷新", command=self._refresh_ports,
               width=5, bg="#333355", fg="white",
               relief=FLAT, cursor="hand2").pack(side=LEFT, padx=2)

        # -------- 第二行：控制面板（下拉菜单）--------
        control_card = Frame(main, bg=COLORS["bg_card"], bd=0)
        control_card.pack(fill=X)

        Label(control_card, text="控制面板",
              font=("微软雅黑", 11, "bold"),
              fg=COLORS["neon"], bg=COLORS["bg_card"]).pack(anchor=W, padx=15, pady=(12, 5))

        # 模式切换区域（默认展开）
        mode_section = CollapsibleSection(control_card, "模式切换", default_open=True)
        mode_section.pack(fill=X, padx=15, pady=(0, 10))
        mode_content = mode_section.get_content()

        mode_inner = Frame(mode_content, bg=COLORS["bg_card"])
        mode_inner.pack(pady=5)

        btn_style = {
            "font": ("微软雅黑", 11, "bold"),
            "width": 12, "height": 2,
            "relief": RAISED, "bd": 2,
            "cursor": "hand2"
        }

        self.auto_btn = Button(mode_inner, text="自动模式",
                             bg=COLORS["accent"], fg="white",
                             activebackground=COLORS["accent_light"], **btn_style,
                             command=self._set_auto_mode)
        self.auto_btn.pack(side=LEFT, padx=5)

        self.manual_btn = Button(mode_inner, text="手动模式",
                              bg=COLORS["shadow"], fg=COLORS["neon"],
                              activebackground=COLORS["accent"], **btn_style,
                              command=self._set_manual_mode)
        self.manual_btn.pack(side=LEFT, padx=5)

        # 快速动作区域（默认展开便于测试）
        action_section = CollapsibleSection(control_card, "快速动作", default_open=True)
        action_section.pack(fill=X, padx=15, pady=(0, 10))
        action_content = action_section.get_content()

        action_inner = Frame(action_content, bg=COLORS["bg_card"])
        action_inner.pack(pady=5)

        actions = [
            ("张开", "O", "#00aa55"),
            ("闭合", "C", "#cc3355"),
            ("握手", "H", "#0066aa"),
            ("捏取", "P", "#6600aa"),
            ("全握", "G", "#aa6600"),
            ("指向", "F", "#008866"),
            ("放松", "R", "#666666"),
        ]

        self.action_btns = []
        for i, (text, cmd, color) in enumerate(actions):
            btn = Button(action_inner, text=f"{text}",
                       command=lambda c=cmd, t=text: self._send_action(c, t),
                       width=8, height=1, font=("微软雅黑", 9),
                       bg=color, fg="white", relief=RAISED, bd=2,
                       state=DISABLED, cursor="hand2")
            btn.grid(row=0, column=i, padx=3, pady=3)
            self.action_btns.append(btn)

        # -------- 日志区 --------
        log_card = Frame(main, bg=COLORS["bg_card"], bd=0)
        log_card.pack(fill=BOTH, expand=True, pady=(15, 0))

        Label(log_card, text="通信日志",
              font=("微软雅黑", 10, "bold"),
              fg=COLORS["text_dim"], bg=COLORS["bg_card"]).pack(anchor=W, padx=15, pady=(10, 5))

        log_frame = Frame(log_card, bg="#0a0a1e")
        log_frame.pack(fill=BOTH, expand=True, padx=15, pady=(0, 10))

        self.log_text = Text(log_frame, height=4, bg="#0a0a1e",
                           fg=COLORS["neon_green"], font=("Consolas", 9),
                           relief=FLAT, bd=0)
        self.log_text.pack(fill=BOTH, expand=True)

        Scrollbar(log_frame, orient=VERTICAL,
                 command=self.log_text.yview).pack(side=RIGHT, fill=Y)
        self.log_text.config(yscrollcommand=lambda f, v: f.yview_moveto(v))

    def _refresh_ports(self):
        ports = list(serial.tools.list_ports.comports())
        self.port_combo['values'] = [p.device for p in ports]
        if ports:
            self.port_combo.current(0)

    def _set_btns_state(self, state):
        """设置动作按钮状态（不改变模式切换按钮）"""
        for btn in self.action_btns:
            btn.config(state=state)

    def _update_mode_display(self):
        if self.is_auto_mode:
            self.mode_label.config(text="模式: 自动", fg=COLORS["neon_green"])
            self.auto_btn.config(bg=COLORS["neon_green"], fg="white")
            self.manual_btn.config(bg=COLORS["shadow"], fg=COLORS["neon"])
            self._set_btns_state(DISABLED)
            self.status_label.config(text="状态: 自动跟随距离")
        else:
            self.mode_label.config(text="模式: 手动", fg=COLORS["neon_orange"])
            self.auto_btn.config(bg=COLORS["shadow"], fg=COLORS["neon"])
            self.manual_btn.config(bg=COLORS["neon_orange"], fg="white")
            self._set_btns_state(NORMAL)
            self.status_label.config(text="状态: 手动控制")

    def _connect(self):
        port = self.port_combo.get()
        if not port:
            messagebox.showwarning("警告", "请选择串口")
            return
        try:
            self.serial_port = serial.Serial(port, 9600, timeout=0.5)
            self.is_connected = True
            self.is_receiving = True
            self.status_led.config(fg=COLORS["neon_green"])
            self.conn_label.config(text="已连接", fg=COLORS["neon_green"])
            self.is_auto_mode = True
            self._update_mode_display()
            self.receive_thread = threading.Thread(target=self._receive_data, daemon=True)
            self.receive_thread.start()
            self._update_loop()
            self._log(f"连接成功: {port}")
        except Exception as e:
            messagebox.showerror("错误", f"连接失败: {e}")

    def _disconnect(self):
        self.is_receiving = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self.status_led.config(fg=COLORS["danger"])
        self.conn_label.config(text="未连接", fg=COLORS["danger"])
        self.mode_label.config(text="模式: 未知", fg=COLORS["text_dim"])
        self.gauge.set_value(0)
        self.tilt.set_angle(0)
        self._set_btns_state(DISABLED)
        self.status_label.config(text="状态: 请先连接")
        self._log("连接已断开")

    def _receive_data(self):
        buffer = ""
        while self.is_receiving and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self._parse_line(line)
            except Exception as e:
                self._log(f"接收错误: {e}")
                break

    def _parse_line(self, line):
        if line.startswith("DIST:"):
            try:
                self.distance = int(line[5:])
            except ValueError:
                pass
        elif line.startswith("ANGLE:"):
            try:
                self.angle = int(line[6:])
            except ValueError:
                pass
        elif line.startswith("MODE:"):
            mode_num = line[5:].strip()
            self.is_auto_mode = (mode_num == "3")

    def _update_loop(self):
        if not self.is_connected:
            return
        self.gauge.set_value(self.distance)
        self.tilt.set_angle(self.angle)
        self._update_mode_display()
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(b'?')
            except:
                pass
        if self.is_connected:
            self.root.after(200, self._update_loop)

    def _set_auto_mode(self):
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
        if not self.is_connected:
            messagebox.showwarning("警告", "请先连接串口")
            return
        try:
            self.serial_port.write(b'M')
            self.is_auto_mode = False
            self._update_mode_display()
            self._log("切换到手动模式")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _send_action(self, cmd, name):
        if not self.is_connected:
            return
        try:
            self.serial_port.write(cmd.encode())
            self.status_label.config(text=f"状态: {name}")
            self._log(f"发送: {name}")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _log(self, msg):
        self.log_text.config(state=NORMAL)
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert(END, f"[{ts}] {msg}\n")
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = UhandControlGUI()
    app.run()
