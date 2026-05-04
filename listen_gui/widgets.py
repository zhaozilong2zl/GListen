"""
Listen 复用组件。对标 Claude Design 稿里的 Section / Row / Switch / Segmented / Kbd / Pill。

tkinter 原生没有这些组件，全都是 Frame + Label + Button 组合。不用 ttk（ttk 样式和我们
的自定义配色不好配合），直接用 tk 控件自绘。
"""
import tkinter as tk
from . import theme as T


# ---------- 基础 Frame 布局 ----------
class Section(tk.Frame):
    """白色卡片容器，顶部有灰色标题条。
    body: 用于放 rows 的 frame
    header: 标题栏 frame，外面可以 pack 按钮/Pill 进去（`sec.header` 作 parent）
    """

    def __init__(self, parent, fonts, title=None, **kw):
        super().__init__(parent, bg=T.BG_CARD, highlightthickness=1,
                         highlightbackground=T.BORDER, **kw)
        self.fonts = fonts
        self.header: tk.Frame = None  # 仅有 title 时存在
        if title:
            head = tk.Frame(self, bg=T.N_25)
            head.pack(fill="x")
            self.header = head
            lbl = tk.Label(
                head, text=title.upper(), bg=T.N_25, fg=T.TEXT_MUTED,
                font=fonts.tiny, anchor="w",
            )
            lbl.pack(side="left", padx=14, pady=(10, 8))
            sep = tk.Frame(self, bg=T.BORDER, height=1)
            sep.pack(fill="x")
        self._rows_holder = tk.Frame(self, bg=T.BG_CARD)
        self._rows_holder.pack(fill="both", expand=True)

    @property
    def body(self) -> tk.Frame:
        return self._rows_holder


class Row(tk.Frame):
    """一行：左侧标题+副标题，右侧控件槽。底部带分割线。
    subtitle 的 wraplength 硬编码 320 —— 窗口 760 - 侧栏 220 - 卡片 padding - control_slot
    ≈ 320 px 可用，超过就换行。固定值比 <Configure> 事件可靠（事件有时初始不触发）。
    """
    SUBTITLE_WRAP = 320

    def __init__(self, parent, fonts, title, subtitle=None, last=False, **kw):
        super().__init__(parent, bg=T.BG_CARD, **kw)
        self.fonts = fonts

        inner = tk.Frame(self, bg=T.BG_CARD)
        inner.pack(fill="x", padx=14, pady=10)

        # 先 pack control_slot（右）让它 claim 自己宽度，再 pack left 占剩余
        self.control_slot = tk.Frame(inner, bg=T.BG_CARD)
        self.control_slot.pack(side="right", padx=(12, 0))
        left = tk.Frame(inner, bg=T.BG_CARD)
        left.pack(side="left", fill="x", expand=True)

        tk.Label(left, text=title, bg=T.BG_CARD, fg=T.TEXT,
                 font=fonts.body, anchor="w", justify="left").pack(anchor="w")

        if subtitle:
            tk.Label(
                left, text=subtitle, bg=T.BG_CARD, fg=T.TEXT_MUTED,
                font=fonts.small, anchor="w", justify="left",
                wraplength=self.SUBTITLE_WRAP,
            ).pack(anchor="w", pady=(2, 0))

        if not last:
            tk.Frame(self, bg=T.BORDER, height=1).pack(fill="x")


# ---------- 原子控件 ----------
class Switch(tk.Frame):
    """拟物化开关。宽 34 高 20，圆点 16，on 状态蓝色。"""

    def __init__(self, parent, value=False, on_change=None, **kw):
        super().__init__(parent, bg=T.BG_CARD, **kw)
        self._value = value
        self._on_change = on_change
        # 用 Canvas 绘制
        self._canvas = tk.Canvas(self, width=34, height=20, bg=T.BG_CARD,
                                 highlightthickness=0, cursor="hand2")
        self._canvas.pack()
        self._canvas.bind("<Button-1>", self._toggle)
        self._track = self._canvas.create_oval(0, 0, 34, 20, fill=T.N_200, outline="")
        # 轨道其实是 rounded rect，用两个圆 + 一个矩形
        self._canvas.delete(self._track)
        self._draw()

    def _draw(self):
        self._canvas.delete("all")
        track_color = T.ACCENT if self._value else T.N_200
        # rounded rect: 两端圆 + 中间矩形
        self._canvas.create_oval(0, 0, 20, 20, fill=track_color, outline="")
        self._canvas.create_oval(14, 0, 34, 20, fill=track_color, outline="")
        self._canvas.create_rectangle(10, 0, 24, 20, fill=track_color, outline="")
        # knob
        x = 16 if self._value else 2
        self._canvas.create_oval(x, 2, x + 16, 18, fill="white", outline=T.BORDER_STRONG)

    def _toggle(self, _e):
        self.set(not self._value)
        if self._on_change:
            self._on_change(self._value)

    def get(self):
        return self._value

    def set(self, v):
        self._value = bool(v)
        self._draw()


class Segmented(tk.Frame):
    """分段选择器。options = [(value, label), ...]"""

    def __init__(self, parent, fonts, options, value=None, on_change=None, **kw):
        super().__init__(parent, bg=T.N_75, highlightthickness=1,
                         highlightbackground=T.BORDER, **kw)
        self.fonts = fonts
        self._on_change = on_change
        self._value = value if value is not None else (options[0][0] if options else None)
        self._buttons = {}
        for i, (val, label) in enumerate(options):
            b = tk.Button(
                self, text=label, font=fonts.small,
                relief="flat", borderwidth=0, highlightthickness=0,
                padx=11, pady=4, cursor="hand2",
                command=lambda v=val: self._pick(v),
            )
            b.pack(side="left", padx=(2 if i == 0 else 1, 1), pady=2)
            self._buttons[val] = b
        self._paint()

    def _pick(self, v):
        if v != self._value:
            self._value = v
            self._paint()
            if self._on_change:
                self._on_change(v)

    def _paint(self):
        for v, b in self._buttons.items():
            if v == self._value:
                b.configure(bg=T.N_0, fg=T.TEXT,
                            activebackground=T.N_0, activeforeground=T.TEXT)
            else:
                b.configure(bg=T.N_75, fg=T.TEXT_MUTED,
                            activebackground=T.N_75, activeforeground=T.TEXT)

    def get(self):
        return self._value

    def set(self, v):
        self._pick(v)


class Kbd(tk.Frame):
    """键帽外观：白底+渐变感（tkinter 做不出渐变，退化为纯白+阴影效果）。"""

    def __init__(self, parent, fonts, text, **kw):
        super().__init__(parent, bg=T.BG_CARD, **kw)
        lbl = tk.Label(
            self, text=text, font=fonts.kbd, fg=T.N_700, bg="#f4f5f8",
            padx=8, pady=3, borderwidth=1, relief="solid",
            highlightthickness=0,
        )
        lbl.pack()
        # tk 没法画底边粗一点的效果，凑合用
        self._label = lbl

    def set_text(self, text):
        self._label.configure(text=text)


class Pill(tk.Label):
    """小胶囊标签。tone in {default, blue, green, orange, red}"""

    TONE_MAP = {
        "default": (T.PILL_DEFAULT_BG, T.PILL_DEFAULT_FG),
        "blue":    (T.PILL_BLUE_BG, T.PILL_BLUE_FG),
        "green":   (T.PILL_GREEN_BG, T.PILL_GREEN_FG),
        "orange":  (T.PILL_ORANGE_BG, T.PILL_ORANGE_FG),
        "red":     (T.PILL_RED_BG, T.PILL_RED_FG),
    }

    def __init__(self, parent, fonts, text, tone="default", **kw):
        bg, fg = self.TONE_MAP.get(tone, self.TONE_MAP["default"])
        super().__init__(parent, text=text, font=fonts.tiny,
                         bg=bg, fg=fg, padx=8, pady=2, **kw)

    def set_tone(self, tone):
        bg, fg = self.TONE_MAP.get(tone, self.TONE_MAP["default"])
        self.configure(bg=bg, fg=fg)


class Button(tk.Button):
    """标准按钮。variant in {default, primary, ghost, header, danger}
    header: Section 标题栏里的按钮，bg 和 N_25 head 背景对比更清晰
    """

    STYLES = {
        "default": dict(bg=T.N_0, fg=T.TEXT, activebackground=T.N_50,
                        bd=1, relief="solid"),
        "primary": dict(bg=T.ACCENT, fg="white", activebackground=T.BLUE_700,
                        bd=0, relief="flat"),
        "ghost":   dict(bg=T.BG_APP, fg=T.TEXT_MUTED, activebackground=T.N_75,
                        bd=0, relief="flat"),
        "header":  dict(bg=T.N_0, fg=T.ACCENT, activebackground=T.BLUE_50,
                        bd=1, relief="solid"),
        "danger":  dict(bg=T.N_0, fg=T.DANGER, activebackground="#fef2f2",
                        bd=1, relief="solid"),
    }

    def __init__(self, parent, fonts, text, command=None, variant="default", **kw):
        style = self.STYLES.get(variant, self.STYLES["default"]).copy()
        style.update(kw)
        super().__init__(parent, text=text, font=fonts.small,
                         command=command, padx=11, pady=5, cursor="hand2",
                         highlightthickness=0, **style)
