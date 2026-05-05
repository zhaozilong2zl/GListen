"""History 页 —— Variant B 时间轴 + 装饰波形。

- 顶部：搜索框 + 筛选（全部/今天/最近7天）+ 刷新按钮
- 顶部三张统计卡：今日条数 / 累计录音分钟 / DB 大小
- 主体：按时间降序列表，每条:
    左 84px  时间 HH:MM + "Today / Yesterday / MM-DD"
    中 18px  圆点 + 连接线（最后一条无线）
    右       识别文本 + Canvas 波形 + 时长 + 语言 Pill + WM_CLASS
- hover 显示右侧按钮：Copy（复制到剪贴板）/ Delete（删除记录）

波形是基于 id 的伪随机 sin 组合，不是真音频——和 Claude Design 稿一样做装饰。
"""
import math
import re
import subprocess
import tkinter as tk
from datetime import datetime, timedelta
from typing import List, Tuple

import history as vi_history
from .. import theme as T
from ..widgets import Pill, Button


# 是否含中文字符（用于 ZH / EN Pill）
_CJK_RE = re.compile(r"[一-鿿]")


def _lang_of(text: str) -> str:
    return "ZH" if _CJK_RE.search(text or "") else "EN"


def _relative_day(ts: float) -> str:
    """把时间戳转成日期标签：Today / Yesterday / MM-DD。"""
    d = datetime.fromtimestamp(ts).date()
    today = datetime.now().date()
    diff = (today - d).days
    if diff == 0:
        return "Today"
    if diff == 1:
        return "Yesterday"
    if diff < 7:
        return d.strftime("%a")  # Mon / Tue
    return d.strftime("%m-%d")


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n/1024:.1f} KB"
    return f"{n/1024**2:.1f} MB"


def _fmt_duration(ms) -> str:
    if not ms:
        return "—"
    return f"{ms/1000:.1f}s"


def make_waveform(parent, seed: int, width=140, height=20,
                  color=T.ACCENT, bg=T.BG_CARD) -> tk.Canvas:
    """装饰用波形 —— 基于 seed 生成的 sin 组合，不代表真实音频。
    用函数而不是 Canvas 子类 —— Python 3.8 tkinter 子类化 Canvas 会在某些情况下
    把 self._w 误设为 width 值（"invalid command 110" 异常），绕开。
    """
    BARS = 48
    BAR_W = 2
    BAR_GAP = 1

    canvas = tk.Canvas(parent, width=width, height=height, bg=bg,
                       highlightthickness=0)
    step = BAR_W + BAR_GAP
    for i in range(BARS):
        x = i * step + 1
        if x + BAR_W > width:
            break
        v = (abs(math.sin(i * 0.73 + seed * 1.37)) * 0.6
             + abs(math.sin(i * 0.21 + seed * 0.53)) * 0.4)
        bar_h = max(2, int(v * height))
        y0 = (height - bar_h) // 2
        y1 = y0 + bar_h
        canvas.create_rectangle(x, y0, x + BAR_W, y1,
                                fill=color, outline="")
    return canvas


class HistoryPage(tk.Frame):
    def __init__(self, parent, fonts, shell):
        super().__init__(parent, bg=T.BG_APP)
        self.fonts = fonts
        self.shell = shell
        self._filter = "all"   # all | today | 7days
        self._search = ""
        self._rows_frame = None
        self._stats_frame = None
        self._row_widgets = []

        self._build_toolbar()
        self._build_stats()
        self._build_list()
        self.refresh()

    # ---------- 顶部工具栏 ----------
    def _build_toolbar(self):
        bar = tk.Frame(self, bg=T.BG_APP)
        bar.pack(fill="x", pady=(0, 12))

        # 搜索框
        search_wrap = tk.Frame(bar, bg=T.N_0, highlightthickness=1,
                               highlightbackground=T.BORDER_STRONG)
        search_wrap.pack(side="left")
        tk.Label(search_wrap, text="搜索", bg=T.N_0, fg=T.TEXT_SUBTLE,
                 font=self.fonts.small, padx=8).pack(side="left")
        self._search_var = tk.StringVar()
        ent = tk.Entry(search_wrap, textvariable=self._search_var,
                       font=self.fonts.small, bg=T.N_0, fg=T.TEXT,
                       relief="flat", bd=0, highlightthickness=0,
                       insertbackground=T.TEXT, width=28)
        ent.pack(side="left", ipady=5, padx=(0, 6))
        self._search_var.trace_add("write", lambda *a: self._on_search())

        # 筛选 Segmented
        seg = tk.Frame(bar, bg=T.N_75, highlightthickness=1,
                       highlightbackground=T.BORDER)
        seg.pack(side="left", padx=(10, 0))
        self._filter_btns = {}
        for val, label in [("all", "全部"), ("today", "今天"), ("7days", "最近 7 天")]:
            b = tk.Button(
                seg, text=label, font=self.fonts.small,
                relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
                highlightthickness=0,
                command=lambda v=val: self._set_filter(v),
            )
            b.pack(side="left", padx=1, pady=1)
            self._filter_btns[val] = b
        self._paint_filter()

        # 右侧：刷新
        Button(bar, self.fonts, "刷新",
               command=self.refresh, variant="ghost").pack(side="right")

    def _on_search(self):
        self._search = self._search_var.get().strip()
        self.refresh()

    def _set_filter(self, v):
        self._filter = v
        self._paint_filter()
        self.refresh()

    def _paint_filter(self):
        for val, b in self._filter_btns.items():
            if val == self._filter:
                b.configure(bg=T.N_0, fg=T.TEXT,
                            activebackground=T.N_0, activeforeground=T.TEXT)
            else:
                b.configure(bg=T.N_75, fg=T.TEXT_MUTED,
                            activebackground=T.N_75, activeforeground=T.TEXT)

    # ---------- 统计卡片 ----------
    def _build_stats(self):
        self._stats_frame = tk.Frame(self, bg=T.BG_APP)
        self._stats_frame.pack(fill="x", pady=(0, 12))

    def _render_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        s = vi_history.stats()
        cards = [
            ("今日", f"{s['today']}", "条"),
            ("累计录音", f"{s['total_minutes']}", "分钟"),
            ("存储", _fmt_size(s['db_bytes']), f"{s['total']} 条"),
        ]
        for i, (title, value, unit) in enumerate(cards):
            card = tk.Frame(self._stats_frame, bg=T.BG_CARD,
                            highlightthickness=1, highlightbackground=T.BORDER)
            card.pack(side="left", fill="x", expand=True,
                      padx=(0 if i == 0 else 8, 0))
            tk.Label(card, text=title, bg=T.BG_CARD, fg=T.TEXT_SUBTLE,
                     font=self.fonts.tiny, anchor="w"
                     ).pack(anchor="w", padx=14, pady=(10, 2))
            val_row = tk.Frame(card, bg=T.BG_CARD)
            val_row.pack(anchor="w", padx=14, pady=(0, 10))
            tk.Label(val_row, text=value, bg=T.BG_CARD, fg=T.TEXT,
                     font=self.fonts.title).pack(side="left")
            tk.Label(val_row, text=" " + unit, bg=T.BG_CARD, fg=T.TEXT_MUTED,
                     font=self.fonts.small).pack(side="left", padx=(4, 0), pady=(6, 0))

    # ---------- 列表 ----------
    def _build_list(self):
        self._list_container = tk.Frame(self, bg=T.BG_CARD,
                                        highlightthickness=1,
                                        highlightbackground=T.BORDER)
        self._list_container.pack(fill="both", expand=True)
        self._rows_frame = tk.Frame(self._list_container, bg=T.BG_CARD)
        self._rows_frame.pack(fill="both", expand=True, padx=0, pady=0)

    def refresh(self):
        self._render_stats()
        self._render_rows()

    def _render_rows(self):
        for w in self._rows_frame.winfo_children():
            w.destroy()
        self._row_widgets = []

        # 查询：用 history.query 已有字段 today/since_days
        kwargs = {"limit": 200}
        if self._filter == "today":
            kwargs["today"] = True
        elif self._filter == "7days":
            kwargs["since_days"] = 7
        if self._search:
            kwargs["search"] = self._search
        try:
            rows = vi_history.query(**kwargs)
        except Exception as e:
            tk.Label(self._rows_frame, text=f"查询失败: {e}",
                     bg=T.BG_CARD, fg=T.DANGER, font=self.fonts.small,
                     padx=20, pady=20).pack()
            return

        if not rows:
            tk.Label(self._rows_frame,
                     text="（没有记录。按住热键说一句就会出现在这里）",
                     bg=T.BG_CARD, fg=T.TEXT_SUBTLE, font=self.fonts.small,
                     padx=20, pady=30).pack()
            return

        for i, row in enumerate(rows):
            is_last = (i == len(rows) - 1)
            self._render_row(row, is_last)

    def _render_row(self, row: Tuple, is_last: bool):
        _id, ts, text, dur_ms, wm_class, win_title = row

        container = tk.Frame(self._rows_frame, bg=T.BG_CARD)
        container.pack(fill="x")

        row_frame = tk.Frame(container, bg=T.BG_CARD)
        row_frame.pack(fill="x", padx=16, pady=(14, 12))

        # ----- 左：时间 -----
        when = datetime.fromtimestamp(ts)
        left = tk.Frame(row_frame, bg=T.BG_CARD)
        left.pack(side="left", anchor="n")
        left.configure(width=76)
        left.pack_propagate(False)
        tk.Label(left, text=when.strftime("%H:%M"),
                 bg=T.BG_CARD, fg=T.TEXT_MUTED,
                 font=self.fonts.kbd, anchor="w"
                 ).pack(anchor="w")
        tk.Label(left, text=_relative_day(ts),
                 bg=T.BG_CARD, fg=T.TEXT_SUBTLE,
                 font=self.fonts.tiny, anchor="w"
                 ).pack(anchor="w", pady=(2, 0))

        # ----- 中：时间轴点 + 连接线（Canvas）-----
        dot_canvas = tk.Canvas(row_frame, width=18, height=60,
                               bg=T.BG_CARD, highlightthickness=0)
        dot_canvas.pack(side="left", anchor="n")
        # 圆点
        cx, cy = 9, 8
        dot_canvas.create_oval(cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5,
                               fill=T.ACCENT, outline="")
        # 淡色 ring
        dot_canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6,
                               fill="", outline="#bfdbfe", width=1.5)
        # 连接线（除最后一条）
        if not is_last:
            dot_canvas.create_line(cx, cy + 8, cx, 60,
                                   fill=T.BORDER, width=1)

        # ----- 右：文本 + meta + hover 操作 -----
        right = tk.Frame(row_frame, bg=T.BG_CARD)
        right.pack(side="left", anchor="n", fill="x", expand=True,
                   padx=(8, 0))

        # hover 操作（右侧）先 pack 占位
        actions = tk.Frame(right, bg=T.BG_CARD)
        actions.pack(side="right", anchor="n")
        # 默认隐藏，hover 时显示
        copy_btn = Button(actions, self.fonts, "复制",
                          command=lambda t=text: self._copy(t),
                          variant="ghost")
        del_btn = Button(actions, self.fonts, "删除",
                         command=lambda rid=_id: self._delete(rid),
                         variant="danger")
        # 默认不 pack —— hover 时 pack
        self._hide_actions = lambda c=copy_btn, d=del_btn: (
            c.pack_forget(), d.pack_forget()
        )
        self._show_actions = lambda c=copy_btn, d=del_btn: (
            c.pack(side="left", padx=(0, 4)),
            d.pack(side="left"),
        )

        # 文本主体
        body_text = tk.Label(right, text=text,
                             bg=T.BG_CARD, fg=T.TEXT,
                             font=self.fonts.body, anchor="w",
                             justify="left", wraplength=380)
        body_text.pack(anchor="w", fill="x")

        # meta: 波形 + lang + dur + target
        meta = tk.Frame(right, bg=T.BG_CARD)
        meta.pack(anchor="w", fill="x", pady=(6, 0))
        make_waveform(meta, seed=_id, width=110, height=18).pack(side="left")
        tk.Label(meta, text="  ", bg=T.BG_CARD).pack(side="left")
        lang = _lang_of(text)
        Pill(meta, self.fonts, lang,
             tone="orange" if lang == "ZH" else "blue").pack(side="left")
        tk.Label(meta, text=f"  {_fmt_duration(dur_ms)}",
                 bg=T.BG_CARD, fg=T.TEXT_SUBTLE,
                 font=self.fonts.tiny).pack(side="left")
        target = wm_class or "—"
        tk.Label(meta, text=f"  →  {target}",
                 bg=T.BG_CARD, fg=T.TEXT_SUBTLE,
                 font=self.fonts.tiny).pack(side="left")

        # 底部分隔线
        if not is_last:
            tk.Frame(container, bg=T.BORDER, height=1).pack(fill="x", padx=16)

        # hover 绑定（给 row_frame 及其所有子 widget）—— Label 子 widget 也要绑，
        # 不然鼠标移到子 widget 上会触发 Leave
        def enter(_e, c=copy_btn, d=del_btn):
            c.pack(side="left", padx=(0, 4))
            d.pack(side="left")

        def leave(_e, c=copy_btn, d=del_btn, rf=row_frame):
            # 只在真的离开 row_frame 时 hide —— 子 widget 之间切换也会触发 <Leave>
            x, y = rf.winfo_pointerx(), rf.winfo_pointery()
            x0, y0 = rf.winfo_rootx(), rf.winfo_rooty()
            x1, y1 = x0 + rf.winfo_width(), y0 + rf.winfo_height()
            if x0 <= x < x1 and y0 <= y < y1:
                return
            c.pack_forget()
            d.pack_forget()

        for w in (row_frame, body_text, meta, left, right):
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)

    # ---------- 操作 ----------
    def _copy(self, text: str):
        try:
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=(text or "").encode("utf-8"),
                           timeout=2, check=True)
            self.shell.toast("已复制到剪贴板")
        except Exception as e:
            self.shell.toast(f"复制失败: {e}", tone="red")

    def _delete(self, row_id: int):
        # 直接删，不弹确认 —— 误删能再说一遍，不值得打断流程
        try:
            import sqlite3
            conn = sqlite3.connect(str(vi_history._db_path()))
            conn.execute("DELETE FROM history WHERE id = ?", (row_id,))
            conn.commit()
            conn.close()
            self.refresh()
            self.shell.toast("已删除")
        except Exception as e:
            self.shell.toast(f"删除失败: {e}", tone="red")
