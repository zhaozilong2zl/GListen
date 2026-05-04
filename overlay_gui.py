#!/usr/bin/env python3
"""
语音输入悬浮框子进程。用系统 /usr/bin/python3 跑，因为 anaconda 的 libtk
没链 libXft/libfontconfig，无法渲染 Noto CJK（会 fallback 到 X core fixed 字体）。

协议：从 stdin 逐行读 JSON，每行一条命令：
  {"cmd": "show"}                 # 弹出到鼠标附近
  {"cmd": "text", "text": "..."}  # 更新显示文字
  {"cmd": "hide"}                 # 淡出隐藏
  {"cmd": "quit"}                 # 退出 mainloop

stdin EOF 或收到 quit 后退出。
"""
import json
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont


ALPHA = 0.92
FADE_MS = 280
BG = "#1c1c1e"
BORDER = "#3a3a3c"
FG = "#ffffff"
FG_IDLE = "#8e8e93"
DOT_COLOR = "#ff453a"
DOT_DIM = "#7a2420"
FONT_SIZE = 15
PLACEHOLDER = "聆听中…"
CJK_CANDIDATES = (
    "Noto Sans CJK SC",
    "Source Han Sans CN",
    "WenQuanYi Micro Hei",
    "WenQuanYi Zen Hei",
    "Sarasa Gothic SC",
    "Microsoft YaHei",
    "DejaVu Sans",
)


class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", ALPHA)
        try:
            self.root.attributes("-type", "splash")
        except Exception:
            pass
        self.root.configure(bg=BORDER)

        available = set(tkfont.families(root=self.root))
        family = next((f for f in CJK_CANDIDATES if f in available), None)
        if family is None:
            family = tkfont.nametofont("TkDefaultFont").actual("family")
        self.text_font = tkfont.Font(root=self.root, family=family, size=FONT_SIZE)
        self.dot_font = tkfont.Font(root=self.root, family=family, size=FONT_SIZE + 2)

        content = tk.Frame(self.root, bg=BG)
        content.pack(padx=1, pady=1, fill="both", expand=True)

        self.dot = tk.Label(
            content, text="●", font=self.dot_font,
            fg=DOT_COLOR, bg=BG,
        )
        self.dot.pack(side="left", padx=(14, 8), pady=10)

        # wraplength 按屏幕宽度自适应：最多 640，且不超过屏幕宽度的 60%
        sw = self.root.winfo_screenwidth()
        wrap = min(640, int(sw * 0.6))
        self.label = tk.Label(
            content, text=PLACEHOLDER, font=self.text_font,
            fg=FG_IDLE, bg=BG,
            wraplength=wrap, justify="left", anchor="w",
        )
        self.label.pack(side="left", padx=(0, 16), pady=10, fill="both", expand=True)

        self.visible = False
        self.fade_gen = 0
        self.pulse_gen = 0
        self._last_reclamp_ms = 0

    def show(self):
        self.fade_gen += 1
        self.label.config(text=PLACEHOLDER, fg=FG_IDLE)
        self.root.attributes("-alpha", ALPHA)
        x = self.root.winfo_pointerx() + 18
        y = self.root.winfo_pointery() + 22
        self.root.geometry(f"+{x}+{y}")
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        x = min(x, sw - w - 8)
        y = min(y, sh - h - 8)
        self.root.geometry(f"+{max(8, x)}+{max(8, y)}")
        self.root.deiconify()
        self.root.lift()
        self.visible = True
        self._start_pulse()

    def _start_pulse(self):
        self.pulse_gen += 1
        gen = self.pulse_gen

        def tick(i):
            if gen != self.pulse_gen or not self.visible:
                return
            self.dot.config(fg=DOT_COLOR if (i % 2 == 0) else DOT_DIM)
            self.root.after(550, lambda: tick(i + 1))

        tick(0)

    def set_text(self, text):
        if not self.visible:
            return
        if text:
            self.label.config(text=text, fg=FG)
        else:
            self.label.config(text=PLACEHOLDER, fg=FG_IDLE)
        # 不做 reclamp（update_idletasks 太重，高频调用会让 mainloop 堆积导致显示卡顿）。
        # 位置只在 show() 时 clamp 一次。如果文本长到穿出屏幕，下次 show 会修正。

    def _reclamp_position(self):
        """文本更新后如果窗口超出屏幕边界，把它挪回来。只向上/向左挪，不变小。"""
        self.root.update_idletasks()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        new_x, new_y = x, y
        if y + h > sh - 8:
            new_y = max(8, sh - h - 8)
        if x + w > sw - 8:
            new_x = max(8, sw - w - 8)
        if new_x != x or new_y != y:
            self.root.geometry(f"+{new_x}+{new_y}")

    def hide(self):
        self.fade_gen += 1
        gen = self.fade_gen
        steps = 8
        interval = max(1, FADE_MS // steps)

        def step(i):
            if gen != self.fade_gen:
                return
            alpha = ALPHA * (1.0 - i / steps)
            try:
                self.root.attributes("-alpha", max(0.0, alpha))
            except Exception:
                return
            if i < steps:
                self.root.after(interval, lambda: step(i + 1))
            else:
                try:
                    self.root.withdraw()
                finally:
                    self.visible = False

        step(1)

    def quit(self):
        try:
            self.root.quit()
        except Exception:
            pass


class JsonPipe:
    """stdin_reader 写入最新命令，tk 侧定期读取。
    解决 after(0) 逐条排 callback 导致 mainloop 堆积卡死的问题。
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.pending_show = False
        self.pending_hide = False
        self.pending_quit = False
        self.pending_text = None  # None = 没新文本；str = 最新文本
        self.eof = False

    def feed_line(self, line):
        line = line.strip()
        if not line:
            return
        try:
            cmd = json.loads(line)
        except Exception:
            return
        op = cmd.get("cmd")
        with self.lock:
            if op == "show":
                self.pending_show = True
            elif op == "text":
                self.pending_text = cmd.get("text", "")
            elif op == "hide":
                self.pending_hide = True
            elif op == "quit":
                self.pending_quit = True

    def drain(self):
        """取出所有 pending 命令并清空。返回 (show, text_or_None, hide, quit)。"""
        with self.lock:
            s, t, h, q = self.pending_show, self.pending_text, self.pending_hide, self.pending_quit
            self.pending_show = False
            self.pending_text = None
            self.pending_hide = False
            self.pending_quit = False
        return s, t, h, q


def stdin_reader(pipe):
    """后台线程：逐行读 stdin，存到 JsonPipe。不做任何 tk 操作。"""
    while True:
        line = sys.stdin.readline()
        if not line:
            pipe.eof = True
            break
        pipe.feed_line(line)


def main():
    overlay = Overlay()
    pipe = JsonPipe()

    t = threading.Thread(target=stdin_reader, args=(pipe,), daemon=True)
    t.start()

    def poll():
        """每 50ms 检查 pipe 里有没有新命令，只处理最新的。"""
        show, text, hide, quit_ = pipe.drain()
        if quit_ or pipe.eof:
            overlay.quit()
            return
        if show:
            overlay.show()
        if text is not None:
            overlay.set_text(text)
        if hide:
            overlay.hide()
        overlay.root.after(50, poll)

    overlay.root.after(50, poll)
    overlay.root.mainloop()


if __name__ == "__main__":
    main()
