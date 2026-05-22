#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机械手控制界面 - Apple 风格设计
"""

import serial
import serial.tools.list_ports
import threading
import time
import math
from tkinter import *
from tkinter import ttk, messagebox


# ================= Apple 风格配色 =================
COLORS = {
    "bg":            "#F2F2F7",
    "card":          "#FFFFFF",
    "accent":        "#007AFF",
    "accent_hover":  "#0062CC",
    "text":          "#1C1C1E",
    "text_secondary":"#8E8E93",
    "separator":     "#E5E5EA",
    "success":       "#34C759",
    "danger":        "#FF3B30",
    "warning":       "#FF9500",
    "purple":        "#AF52DE",
    "teal":          "#5AC8FA",
}


class Separator(Frame):
    """分割线"""
    def __init__(self, parent, bg=COLORS["separator"], height=1, **kwargs):
        super().__init__(parent, bg=bg, height=height, **kwargs)


class Card(Frame):
    """卡片容器"""

    def __init__(self, parent, padding=16, **kwargs):
        super().__init__(parent, bg=COLORS["card"], bd=0,
                        highlightthickness=0, **kwargs)
        self.inner = Frame(self, bg=COLORS["card"])
        self.inner.pack(fill=BOTH, expand=True, padx=padding, pady=padding)


# ================= 仪表盘 =================
class GaugeCard(Canvas):

    def __init__(self, parent, title, unit="mm", **kwargs):
        super().__init__(parent, bg=COLORS["card"], highlightthickness=0, **kwargs)
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

        cx, cy, r = w / 2, h / 2 - 14, min(w, h) / 2 - 26

        self.create_arc(cx - r, cy - r, cx + r, cy + r,
                        start=135, extent=270, style=ARC,
                        outline="#E5E5EA", width=10)

        ratio = self.value / self.max_value
        ext = int(ratio * 270)
        if ext > 0:
            if self.value < 80:
                color = COLORS["success"]
            elif self.value < 200:
                color = COLORS["accent"]
            else:
                color = COLORS["warning"]
            self.create_arc(cx - r, cy - r, cx + r, cy + r,
                            start=135, extent=ext, style=ARC,
                            outline=color, width=10)

        self.create_text(cx, cy - 6, text=f"{self.value}",
                        fill=COLORS["text"], font=("", 28, "bold"))
        self.create_text(cx, cy + 22, text=self.unit,
                        fill=COLORS["text_secondary"], font=("", 10))
        self.create_text(cx, cy - r + 10, text=self.title,
                        fill=COLORS["text_secondary"], font=("", 9))


class TiltCard(Canvas):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS["card"], highlightthickness=0, **kwargs)
        self.angle = 0

    def set_angle(self, val):
        self.angle = val
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 40:
            return

        cx, cy, r = w / 2, h / 2 - 12, min(w, h) / 2 - 26

        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                        outline="#E5E5EA", width=2)
        self.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=COLORS["accent"])

        self.create_line(cx - r - 5, cy, cx + r + 5, cy,
                        fill="#E5E5EA", width=1, dash=(4, 4))

        rad = math.radians(90 - self.angle * 2)
        px = cx + (r - 18) * math.cos(rad)
        py = cy - (r - 18) * math.sin(rad)

        color = COLORS["success"] if abs(self.angle) < 10 else COLORS["warning"]
        self.create_line(cx, cy, px, py, fill=color, width=3)
        self.create_oval(px - 6, py - 6, px + 6, py + 6, fill=color)

        self.create_text(cx, cy + r + 18, text=f"{self.angle:.1f}°",
                        fill=COLORS["text"], font=("", 14, "bold"))
        self.create_text(cx, cy - r + 10, text="云台角度",
                        fill=COLORS["text_secondary"], font=("", 9))


# ================= 主界面 =================
class UhandControlGUI:

    def __init__(self):
        self.root = Tk()
        self.root.title("uHand")
        self.root.geometry("780x620")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(720, 560)

        self.serial_port = None
        self.is_connected = False
        self.is_receiving = False
        self.receive_thread = None

        self.distance = 0
        self.angle = 0
        self.is_auto_mode = True

        self._setup_ui()

    def _pill_btn(self, parent, text, command, color=COLORS["accent"],
                  fg="white", state=NORMAL, **kwargs):
        """圆角按钮"""
        return Button(parent, text=text, command=command,
                      font=("", 10), bg=color, fg=fg,
                      activebackground=COLORS["accent_hover"]
                          if color == COLORS["accent"] else "#d0d0d6",
                      activeforeground=fg,
                      relief=FLAT, bd=0, padx=16, pady=7,
                      state=state, cursor="hand2",
                      disabledforeground=COLORS["text_secondary"], **kwargs)

    def _setup_ui(self):
        # ========== 导航栏 ==========
        navbar = Frame(self.root, bg="white", height=44)
        navbar.pack(fill=X)
        navbar.pack_propagate(False)

        Label(navbar, text="uHand", font=("", 17, "bold"),
              fg=COLORS["text"], bg="white").pack(side=LEFT, padx=20, pady=8)

        self.conn_dot = Label(navbar, text="●", font=("", 10),
                              fg=COLORS["danger"], bg="white")
        self.conn_dot.pack(side=RIGHT, padx=(0, 16))

        self.conn_text = Label(navbar, text="未连接", font=("", 11),
                               fg=COLORS["text_secondary"], bg="white")
        self.conn_text.pack(side=RIGHT, padx=4)

        # ========== 主区域 ==========
        main = Frame(self.root, bg=COLORS["bg"])
        main.pack(fill=BOTH, expand=True, padx=20, pady=(16, 20))

        # ---------- 仪表卡片 ----------
        gauge_card = Card(main, padding=20)
        gauge_card.pack(fill=X, pady=(0, 16))

        gauges = Frame(gauge_card.inner, bg=COLORS["card"])
        gauges.pack(fill=X)

        left_gauge = Frame(gauges, bg=COLORS["card"])
        left_gauge.pack(side=LEFT, fill=BOTH, expand=True)
        self.gauge = GaugeCard(left_gauge, "超声波距离", unit="mm",
                               width=200, height=160)
        self.gauge.pack()

        right_gauge = Frame(gauges, bg=COLORS["card"])
        right_gauge.pack(side=LEFT, fill=BOTH, expand=True)
        self.tilt = TiltCard(right_gauge, width=200, height=160)
        self.tilt.pack()

        mid_gauge = Frame(gauges, bg=COLORS["card"])
        mid_gauge.pack(side=LEFT, fill=BOTH, expand=True)

        Label(mid_gauge, text="机械手状态", font=("", 10, "bold"),
              fg=COLORS["text"], bg=COLORS["card"]).pack(anchor=W, pady=(0, 12))

        mode_frame = Frame(mid_gauge, bg=COLORS["card"])
        mode_frame.pack(fill=X, pady=4)
        Label(mode_frame, text="模式", font=("", 10),
              fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(side=LEFT)
        self.mode_label = Label(mode_frame, text="——", font=("", 10, "bold"),
                                fg=COLORS["text_secondary"], bg=COLORS["card"])
        self.mode_label.pack(side=RIGHT)

        Separator(mid_gauge, height=1).pack(fill=X, pady=10)

        dist_frame = Frame(mid_gauge, bg=COLORS["card"])
        dist_frame.pack(fill=X, pady=4)
        Label(dist_frame, text="距离", font=("", 10),
              fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(side=LEFT)
        self.dist_value = Label(dist_frame, text="——", font=("", 20, "bold"),
                                fg=COLORS["text"], bg=COLORS["card"])
        self.dist_value.pack(side=RIGHT)

        Separator(mid_gauge, height=1).pack(fill=X, pady=10)

        angle_frame = Frame(mid_gauge, bg=COLORS["card"])
        angle_frame.pack(fill=X, pady=4)
        Label(angle_frame, text="云台角度", font=("", 10),
              fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(side=LEFT)
        self.angle_value = Label(angle_frame, text="——", font=("", 20, "bold"),
                                 fg=COLORS["text"], bg=COLORS["card"])
        self.angle_value.pack(side=RIGHT)

        Separator(mid_gauge, height=1).pack(fill=X, pady=10)

        status_row = Frame(mid_gauge, bg=COLORS["card"])
        status_row.pack(fill=X, pady=4)
        Label(status_row, text="状态", font=("", 10),
              fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(side=LEFT)
        self.status_label = Label(status_row, text="就绪", font=("", 10, "bold"),
                                  fg=COLORS["text_secondary"], bg=COLORS["card"])
        self.status_label.pack(side=RIGHT)

        # ---------- 串口卡片 ----------
        port_card = Card(main, padding=14)
        port_card.pack(fill=X, pady=(0, 16))

        port_row = Frame(port_card.inner, bg=COLORS["card"])
        port_row.pack(fill=X)

        Label(port_row, text="串口", font=("", 10),
              fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(side=LEFT, padx=(0, 8))

        self.port_combo = ttk.Combobox(port_row, width=16, state="readonly",
                                       font=("", 10))
        self.port_combo.pack(side=LEFT, padx=(0, 8))
        self._refresh_ports()

        self._pill_btn(port_row, "连接", self._connect, COLORS["accent"],
                      width=6).pack(side=LEFT, padx=4)
        self._pill_btn(port_row, "断开", self._disconnect, COLORS["danger"],
                      width=6).pack(side=LEFT, padx=4)

        # ---------- 控制卡片 ----------
        control_card = Card(main, padding=20)
        control_card.pack(fill=X, pady=(0, 16))

        Label(control_card.inner, text="控制模式", font=("", 12, "bold"),
              fg=COLORS["text"], bg=COLORS["card"]).pack(anchor=W, pady=(0, 12))

        mode_row = Frame(control_card.inner, bg=COLORS["card"])
        mode_row.pack(fill=X, pady=(0, 14))

        self.auto_btn = self._pill_btn(mode_row, "自动模式", self._set_auto_mode,
                                       COLORS["accent"], width=14)
        self.auto_btn.pack(side=LEFT, padx=(0, 10))

        self.manual_btn = self._pill_btn(mode_row, "手动模式", self._set_manual_mode,
                                         "#E5E5EA", fg=COLORS["text"], width=14)
        self.manual_btn.pack(side=LEFT)

        Separator(control_card.inner, height=1).pack(fill=X, pady=(0, 14))

        Label(control_card.inner, text="手动控制", font=("", 10),
              fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(anchor=W, pady=(0, 8))

        actions = [
            ("张开", "O", COLORS["accent"]),
            ("闭合", "C", COLORS["danger"]),
            ("握手", "H", COLORS["success"]),
            ("捏取", "P", COLORS["purple"]),
            ("全握", "G", COLORS["warning"]),
            ("指向", "F", COLORS["teal"]),
            ("放松", "R", COLORS["text_secondary"]),
        ]

        action_row = Frame(control_card.inner, bg=COLORS["card"])
        action_row.pack(fill=X)

        self.action_btns = []
        for text, cmd, color in actions:
            btn = self._pill_btn(action_row, text,
                                lambda c=cmd, t=text: self._send_action(c, t),
                                color, state=DISABLED)
            btn.pack(side=LEFT, padx=3)
            self.action_btns.append(btn)

        # ---------- 日志卡片 ----------
        log_card = Card(main, padding=12)
        log_card.pack(fill=BOTH, expand=True)

        Label(log_card.inner, text="日志", font=("", 10, "bold"),
              fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(anchor=W, pady=(0, 6))

        self.log_text = Text(log_card.inner, height=3,
                            bg="#F9F9FB", fg=COLORS["text"],
                            font=("Menlo", 9), relief=FLAT, bd=0,
                            wrap=WORD, state=DISABLED)
        self.log_text.pack(fill=BOTH, expand=True)

    # ================= 串口逻辑 =================

    def _refresh_ports(self):
        ports = list(serial.tools.list_ports.comports())
        self.port_combo['values'] = [p.device for p in ports]
        if ports:
            self.port_combo.current(0)

    def _set_btns_state(self, state):
        for btn in self.action_btns:
            btn.config(state=state)

    def _update_mode_display(self):
        if self.is_auto_mode:
            self.mode_label.config(text="自动", fg=COLORS["success"])
            self.auto_btn.config(bg=COLORS["accent"], fg="white")
            self.manual_btn.config(bg="#E5E5EA", fg=COLORS["text"])
            self._set_btns_state(DISABLED)
            self.status_label.config(text="自动跟随距离",
                                     fg=COLORS["text_secondary"])
        else:
            self.mode_label.config(text="手动", fg=COLORS["warning"])
            self.auto_btn.config(bg="#E5E5EA", fg=COLORS["text"])
            self.manual_btn.config(bg=COLORS["warning"], fg="white")
            self._set_btns_state(NORMAL)
            self.status_label.config(text="手动控制",
                                     fg=COLORS["text_secondary"])

    def _connect(self):
        port = self.port_combo.get()
        if not port:
            messagebox.showwarning("警告", "请选择串口")
            return
        try:
            self.serial_port = serial.Serial(port, 9600, timeout=0.5)
            self.is_connected = True
            self.is_receiving = True
            self.conn_dot.config(fg=COLORS["success"])
            self.conn_text.config(text="已连接", fg=COLORS["success"])
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
        self.conn_dot.config(fg=COLORS["danger"])
        self.conn_text.config(text="未连接", fg=COLORS["text_secondary"])
        self.gauge.set_value(0)
        self.tilt.set_angle(0)
        self.dist_value.config(text="——")
        self.angle_value.config(text="——")
        self.mode_label.config(text="——", fg=COLORS["text_secondary"])
        self._set_btns_state(DISABLED)
        self.status_label.config(text="请先连接", fg=COLORS["text_secondary"])
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
        """解析 Arduino 数据（运行在接收线程中，仅更新变量）"""
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
        """主循环（运行在主线程，安全更新 GUI）"""
        if not self.is_connected:
            return
        # 更新仪表盘
        self.gauge.set_value(self.distance)
        self.tilt.set_angle(self.angle)
        # 更新数值显示
        self.dist_value.config(text=f"{self.distance} mm")
        self.angle_value.config(text=f"{self.angle}°")
        # 更新模式显示
        self._update_mode_display()
        # 请求 Arduino 发送数据
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(b'?')
            except:
                pass
        if self.is_connected:
            self.root.after(200, self._update_loop)

    # ================= 模式/动作 =================

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
            self.status_label.config(text=name, fg=COLORS["text_secondary"])
            self._log(f"发送: {name}")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def _log(self, msg):
        self.log_text.config(state=NORMAL)
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert(END, f"{ts}  {msg}\n")
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = UhandControlGUI()
    app.run()
