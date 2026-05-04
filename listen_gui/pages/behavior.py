"""Behavior 页 —— 输入模式 / 粘贴键 / 悬浮框 / debug。

改动立即 save 到 config.json 并重启 voice-input 服务。服务重启大约 1-2s 中断，
使用场景里用户不会在录音过程中改设置，所以"立改立生效"最直观。
"""
import tkinter as tk
from copy import deepcopy

import config as vi_config
from .. import theme as T
from ..widgets import Section, Row, Switch, Segmented


class BehaviorPage(tk.Frame):
    def __init__(self, parent, fonts, shell):
        super().__init__(parent, bg=T.BG_APP)
        self.fonts = fonts
        self.shell = shell
        self._cfg = vi_config.load()
        self._behavior = self._cfg.setdefault("behavior", {})

        # 可滚动区域：未来字段变多时有 scroll bar；现在短先不加
        # Section 1: 文本输入
        self._sec_input = Section(self, fonts, title="文本输入")
        self._sec_input.pack(fill="x", pady=(0, 12))

        # 输入方式
        row1 = Row(self._sec_input.body, fonts,
                   title="输入方式",
                   subtitle="Paste 绕过中文输入法（推荐）；Type 逐字模拟按键，输入法开着会被拦。")
        row1.pack(fill="x")
        self._mode_seg = Segmented(
            row1.control_slot, fonts,
            options=[("paste", "Paste"), ("type", "Type")],
            value=self._behavior.get("input_mode", "paste"),
            on_change=self._on_mode_change,
        )
        self._mode_seg.pack()

        # 粘贴快捷键
        row2 = Row(self._sec_input.body, fonts,
                   title="粘贴快捷键",
                   subtitle="终端 / Claude Code TUI 用 Ctrl+Shift+V；纯 GUI 应用用 Ctrl+V。")
        row2.pack(fill="x")
        self._paste_seg = Segmented(
            row2.control_slot, fonts,
            options=[("ctrl+shift+v", "Ctrl+Shift+V"), ("ctrl+v", "Ctrl+V")],
            value=self._behavior.get("paste_key", "ctrl+shift+v"),
            on_change=self._on_paste_change,
        )
        self._paste_seg.pack()
        # 第二行是最后一行，去掉分割线 —— 通过重写 last 字段做？Row 构造已 pack，先不处理

        # Section 2: 悬浮框
        self._sec_overlay = Section(self, fonts, title="悬浮框")
        self._sec_overlay.pack(fill="x", pady=(0, 12))

        row3 = Row(self._sec_overlay.body, fonts,
                   title="显示悬浮框",
                   subtitle="按住热键时，鼠标附近弹出黑色 HUD 显示实时识别。")
        row3.pack(fill="x")
        self._overlay_sw = Switch(
            row3.control_slot, value=self._behavior.get("overlay_enabled", True),
            on_change=self._on_overlay_change,
        )
        self._overlay_sw.pack()

        row4 = Row(self._sec_overlay.body, fonts,
                   title="位置",
                   subtitle='当前仅支持跟随鼠标。后续可以做「屏幕角落」、「靠近输入框」等锚点。',
                   last=True)
        row4.pack(fill="x")
        tk.Label(row4.control_slot, text="跟随鼠标",
                 bg=T.BG_CARD, fg=T.TEXT_MUTED, font=fonts.small).pack()

        # Section 3: 识别
        self._sec_recog = Section(self, fonts, title="识别")
        self._sec_recog.pack(fill="x", pady=(0, 12))
        row_punc = Row(self._sec_recog.body, fonts,
                       title="自动加标点",
                       subtitle="豆包按 VAD 分句自动加句号/逗号。关掉能避免「一句话中间停顿就变句号」，但识别结果就没标点了，需要你自己读出来「句号/逗号」。",
                       last=True)
        row_punc.pack(fill="x")
        self._punc_sw = Switch(
            row_punc.control_slot,
            value=self._behavior.get("auto_punctuation", True),
            on_change=self._on_punc_change,
        )
        self._punc_sw.pack()

        # Section 4: 诊断
        self._sec_diag = Section(self, fonts, title="诊断")
        self._sec_diag.pack(fill="x", pady=(0, 12))
        row5 = Row(self._sec_diag.body, fonts,
                   title="调试日志",
                   subtitle="把豆包返回的原始 ASR 帧打印到 journalctl。排查识别问题时打开。",
                   last=True)
        row5.pack(fill="x")
        self._debug_sw = Switch(
            row5.control_slot, value=self._behavior.get("debug", False),
            on_change=self._on_debug_change,
        )
        self._debug_sw.pack()

    # ---------- 保存 callbacks ----------
    def _apply(self):
        cfg = vi_config.load()  # 重新读以防其他页面已改动
        cfg.setdefault("behavior", {}).update(self._behavior)
        self.shell.apply_changes(cfg, restart=True)

    def _on_mode_change(self, v):
        self._behavior["input_mode"] = v
        self._apply()

    def _on_paste_change(self, v):
        self._behavior["paste_key"] = v
        self._apply()

    def _on_overlay_change(self, v):
        self._behavior["overlay_enabled"] = v
        self._apply()

    def _on_debug_change(self, v):
        self._behavior["debug"] = v
        self._apply()

    def _on_punc_change(self, v):
        self._behavior["auto_punctuation"] = v
        self._apply()
