"""Shortcuts 页 —— 主键 hero + 辅助键列表 + 添加/编辑模态 + 冲突提示。

按键捕获用 tkinter 自己的 KeyPress 事件（focus 到特定 widget 后接收所有按键）。
不用 pynput —— GUI 跑系统 python3，可能没装 pynput；而且 tkinter bind 够用。
"""
import tkinter as tk
from copy import deepcopy
from typing import Optional

import config as vi_config
import keys as vi_keys
from .. import theme as T
from ..widgets import Section, Row, Kbd, Pill, Button


# 主键冲突提示表。key = 规范化名字（config 里的形式）
CONFLICTS = {
    "f9":  "在 VSCode / JetBrains 里是「切换断点」的快捷键",
    "f5":  "大多数浏览器用来刷新",
    "f11": "浏览器 / 终端常用来切全屏",
    "caps_lock": "系统默认切换大写，用它录音前要先关掉 Caps Lock 的原生功能",
    "cmd": "GNOME 里 Super 键默认打开 Activities",
}


class KeyCapture(tk.Frame):
    """键位显示 + 捕获。默认显示 Kbd 键帽；点击进入捕获态，按下任意键记录。
    不监听修饰键单独（Shift/Ctrl/Alt）—— 主热键必须是可单独按住的键。

    键盘事件绑到 Toplevel（通过 self.winfo_toplevel()）而非 Frame 本身 —— Linux tkinter
    下 Frame 拿不到 KeyPress（Frame 不是 focusable widget），特别是在模态 Toplevel 里。
    """

    def __init__(self, parent, fonts, value: Optional[str] = None,
                 on_change=None):
        super().__init__(parent, bg=T.BG_CARD,
                         highlightthickness=1.5, highlightbackground=T.BORDER_STRONG)
        self.fonts = fonts
        self._value = value
        self._on_change = on_change
        self._capturing = False
        self._bind_ids = []  # Toplevel 上的 bind id，cancel 时 unbind

        self._label = tk.Label(
            self, text="", bg=T.BG_CARD, font=fonts.kbd,
            fg=T.N_700, padx=14, pady=10,
        )
        self._label.pack()
        self._label.bind("<Button-1>", self._start_capture)
        self.bind("<Button-1>", self._start_capture)
        self._paint()

    def _paint(self):
        if self._capturing:
            self.configure(highlightthickness=2, highlightbackground=T.ACCENT, bg="#f0f6ff")
            self._label.configure(text="按下任意键…", fg=T.ACCENT, bg="#f0f6ff")
        else:
            self.configure(highlightthickness=1, highlightbackground=T.BORDER_STRONG, bg=T.BG_CARD)
            if self._value:
                self._label.configure(
                    text=vi_keys.display_name(self._value),
                    fg=T.N_700, bg="#f4f5f8")
            else:
                self._label.configure(text="未设置", fg=T.TEXT_SUBTLE, bg=T.BG_CARD)

    def _start_capture(self, _e=None):
        if self._capturing:
            return
        self._capturing = True
        top = self.winfo_toplevel()
        # 把 key 事件绑到 Toplevel，确保不管焦点在哪都能收到
        self._bind_ids.append(("<KeyPress>", top.bind("<KeyPress>", self._on_key, "+")))
        top.focus_force()
        self._paint()

    def _cancel(self, _e=None):
        if not self._capturing:
            return
        self._capturing = False
        self._unbind_top()
        self._paint()

    def _unbind_top(self):
        top = self.winfo_toplevel()
        for seq, bid in self._bind_ids:
            try:
                top.unbind(seq, bid)
            except Exception:
                pass
        self._bind_ids = []

    def _on_key(self, event):
        if not self._capturing:
            return
        name = vi_keys.tk_keysym_to_name(event.keysym)
        if name is None:  # 修饰键单独按，忽略等待真正的键
            return "break"
        if name == "esc":
            self._cancel()
            return "break"
        self._value = name
        self._capturing = False
        self._unbind_top()
        self._paint()
        if self._on_change:
            self._on_change(name)
        return "break"  # 吃掉这次按键，避免传给下层（比如 Esc 关 dialog）

    def get(self):
        return self._value

    def set(self, name):
        self._value = name
        self._paint()


# ---------- 主页面 ----------
class ShortcutsPage(tk.Frame):
    def __init__(self, parent, fonts, shell):
        super().__init__(parent, bg=T.BG_APP)
        self.fonts = fonts
        self.shell = shell
        self._cfg = vi_config.load()
        self._hotkeys = self._cfg.setdefault("hotkeys", {})
        self._hotkeys.setdefault("main", {"key": "f9", "label": "Dictate",
                                          "actions": ["paste"], "skip_postprocess": False})
        self._hotkeys.setdefault("auxiliary", [])

        self._build_hero()
        self._build_aux_section()
        self._build_conflicts_section()

    # ---------- Hero 卡 ----------
    def _build_hero(self):
        hero = tk.Frame(self, bg=T.BG_CARD, highlightthickness=1,
                        highlightbackground=T.BORDER)
        hero.pack(fill="x", pady=(0, 12))

        inner = tk.Frame(hero, bg=T.BG_CARD)
        inner.pack(fill="x", padx=22, pady=20)

        left = tk.Frame(inner, bg=T.BG_CARD)
        left.pack(side="left", fill="x", expand=True)

        # 顶部 Pill
        pill_row = tk.Frame(left, bg=T.BG_CARD)
        pill_row.pack(anchor="w")
        Pill(pill_row, self.fonts, "● 主热键", tone="blue").pack(side="left")
        tk.Label(pill_row, text="按住说话", bg=T.BG_CARD, fg=T.TEXT_SUBTLE,
                 font=self.fonts.tiny).pack(side="left", padx=(8, 0))

        tk.Label(left, text="Push-to-talk", bg=T.BG_CARD, fg=T.TEXT,
                 font=self.fonts.title).pack(anchor="w", pady=(8, 3))

        desc_lbl = tk.Label(
            left,
            text="按住这个键全局触发语音识别，松开后执行对应动作链。改动后服务自动重启，新热键立刻生效。",
            bg=T.BG_CARD, fg=T.TEXT_MUTED, font=self.fonts.small,
            anchor="w", justify="left", wraplength=300,
        )
        desc_lbl.pack(anchor="w", fill="x")
        left.bind("<Configure>",
                  lambda e, l=desc_lbl: l.configure(wraplength=max(180, e.width - 8)))

        btn_row = tk.Frame(left, bg=T.BG_CARD)
        btn_row.pack(anchor="w", pady=(14, 0))
        Button(btn_row, self.fonts, "⌨  重新绑定",
               command=self._rebind_main, variant="primary").pack(side="left")
        Button(btn_row, self.fonts, "重置为 F9",
               command=self._reset_main, variant="ghost").pack(side="left", padx=(6, 0))

        # 右侧：KeyCapture
        right = tk.Frame(inner, bg=T.BG_CARD)
        right.pack(side="right", padx=(16, 0))
        self._main_cap = KeyCapture(
            right, self.fonts, value=self._hotkeys["main"].get("key", "f9"),
            on_change=self._on_main_key_change,
        )
        self._main_cap.pack()

    def _rebind_main(self):
        self._main_cap._start_capture()

    def _reset_main(self):
        self._on_main_key_change("f9")
        self._main_cap.set("f9")

    def _on_main_key_change(self, new_key):
        self._hotkeys["main"]["key"] = new_key
        self._apply()
        self._refresh_conflicts()

    # ---------- 辅助键列表 ----------
    def _build_aux_section(self):
        self._sec_aux = Section(self, self.fonts, title="辅助热键")
        self._sec_aux.pack(fill="x", pady=(0, 12))
        # 把"＋ 添加"按钮直接以 header 作 parent 构造，pack 到右侧
        Button(self._sec_aux.header, self.fonts, "＋ 添加",
               command=self._add_aux, variant="header"
               ).pack(side="right", padx=10, pady=6)
        self._aux_list = self._sec_aux.body
        self._render_aux()

    def _render_aux(self):
        # 清空
        for w in self._aux_list.winfo_children():
            w.destroy()
        entries = self._hotkeys.get("auxiliary", [])
        if not entries:
            tk.Label(self._aux_list,
                     text="（没有辅助热键。点击右上角「＋ 添加」可以绑一个，比如 F10 = 录完自动按 Enter 发送）",
                     bg=T.BG_CARD, fg=T.TEXT_SUBTLE, font=self.fonts.small,
                     anchor="w", justify="left", wraplength=600, padx=14, pady=14).pack(anchor="w")
            return
        for i, entry in enumerate(entries):
            self._render_aux_row(entry, i, last=(i == len(entries) - 1))

    def _render_aux_row(self, entry, index, last=False):
        row = tk.Frame(self._aux_list, bg=T.BG_CARD)
        row.pack(fill="x", padx=14, pady=10)
        # 右：编辑 / 删除（side=right 先 pack，占右侧固定宽度 ~140px）
        right = tk.Frame(row, bg=T.BG_CARD)
        right.pack(side="right")
        Button(right, self.fonts, "编辑",
               command=lambda i=index: self._edit_aux(i),
               variant="ghost").pack(side="left", padx=(0, 4))
        Button(right, self.fonts, "删除",
               command=lambda i=index: self._delete_aux(i),
               variant="danger").pack(side="left")
        # 左：Kbd
        Kbd(row, self.fonts, vi_keys.display_name(entry.get("key", "?"))).pack(side="left")
        # 中：label + actions。wraplength 硬编码 220 —— row 总宽 ~440px，减去
        # Kbd(~60) / 按钮区(~140) / padx(~20) ≈ 220 可用，超过就换行避免撑破 right
        mid = tk.Frame(row, bg=T.BG_CARD)
        mid.pack(side="left", padx=(12, 0), fill="both", expand=True)
        tk.Label(mid, text=entry.get("label") or "(未命名)",
                 bg=T.BG_CARD, fg=T.TEXT, font=self.fonts.body,
                 anchor="w", wraplength=220, justify="left").pack(anchor="w")
        desc = self._describe_actions(entry.get("actions") or [])
        tk.Label(mid, text=desc, bg=T.BG_CARD, fg=T.TEXT_MUTED,
                 font=self.fonts.small, anchor="w",
                 justify="left", wraplength=220).pack(anchor="w", pady=(2, 0))
        if not last:
            tk.Frame(self._aux_list, bg=T.BORDER, height=1).pack(fill="x", padx=14)

    def _describe_actions(self, actions):
        if not actions:
            return "(无动作)"
        parts = []
        for a in actions:
            if a == "paste":
                parts.append("粘贴")
            elif a == "clipboard":
                parts.append("复制到剪贴板")
            elif a.startswith("press:"):
                combo = a[6:]
                parts.append(f"按 {combo}")
            else:
                parts.append(a)
        return " → ".join(parts)

    def _add_aux(self):
        AuxDialog(self, self.fonts, entry=None, on_save=self._save_new_aux)

    def _edit_aux(self, index):
        entry = deepcopy(self._hotkeys["auxiliary"][index])
        AuxDialog(self, self.fonts, entry=entry,
                  on_save=lambda new: self._save_edit_aux(index, new))

    def _save_new_aux(self, new_entry):
        self._hotkeys.setdefault("auxiliary", []).append(new_entry)
        self._apply()
        self._render_aux()

    def _save_edit_aux(self, index, new_entry):
        self._hotkeys["auxiliary"][index] = new_entry
        self._apply()
        self._render_aux()

    def _delete_aux(self, index):
        del self._hotkeys["auxiliary"][index]
        self._apply()
        self._render_aux()

    # ---------- 冲突提示 ----------
    def _build_conflicts_section(self):
        self._sec_conflict = Section(self, self.fonts, title="冲突提示")
        self._sec_conflict.pack(fill="x", pady=(0, 12))
        self._conflict_body = self._sec_conflict.body
        self._refresh_conflicts()

    def _refresh_conflicts(self):
        for w in self._conflict_body.winfo_children():
            w.destroy()
        main_key = self._hotkeys["main"].get("key", "")
        notes = []
        msg = CONFLICTS.get(main_key)
        if msg:
            notes.append((main_key, msg))
        if not notes:
            tk.Label(self._conflict_body,
                     text="✓ 没有已知冲突。",
                     bg=T.BG_CARD, fg=T.SUCCESS,
                     font=self.fonts.small, anchor="w",
                     padx=14, pady=12).pack(anchor="w")
            return
        for key, msg in notes:
            line = tk.Frame(self._conflict_body, bg=T.BG_CARD)
            line.pack(fill="x", padx=14, pady=12)
            Kbd(line, self.fonts, vi_keys.display_name(key)).pack(side="left")
            tk.Label(line, text="  " + msg, bg=T.BG_CARD, fg=T.TEXT,
                     font=self.fonts.small, anchor="w",
                     justify="left", wraplength=540).pack(side="left", fill="x", expand=True)

    # ---------- 保存入口 ----------
    def _apply(self):
        cfg = vi_config.load()
        cfg["hotkeys"] = self._hotkeys
        self.shell.apply_changes(cfg, restart=True)


# ---------- 添加/编辑辅助键的模态窗 ----------
class AuxDialog(tk.Toplevel):
    """添加或编辑一条辅助热键。on_save(entry_dict) 回调。"""

    PRESS_OPTIONS = [
        ("", "（不追加按键）"),
        ("Return", "Enter"),
        ("Tab", "Tab"),
        ("shift+Return", "Shift + Enter"),
        ("ctrl+s", "Ctrl + S"),
        ("ctrl+Return", "Ctrl + Enter"),
    ]

    def __init__(self, parent, fonts, entry=None, on_save=None):
        super().__init__(parent)
        self.fonts = fonts
        self._on_save = on_save
        self._entry = entry or {
            "key": None, "label": "", "actions": ["paste"], "skip_postprocess": False,
        }
        self.title("辅助热键")
        self.configure(bg=T.BG_APP)
        self.resizable(False, False)
        # 模态
        self.transient(parent.winfo_toplevel())
        try:
            self.grab_set()
        except Exception:
            pass
        self.bind("<Escape>", lambda _e: self.destroy())

        self._build()
        # 居中
        self.update_idletasks()
        p = parent.winfo_toplevel()
        x = p.winfo_rootx() + (p.winfo_width() - self.winfo_width()) // 2
        y = p.winfo_rooty() + (p.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _build(self):
        body = tk.Frame(self, bg=T.BG_APP)
        body.pack(fill="both", expand=True, padx=22, pady=20)

        tk.Label(body, text="添加辅助热键" if self._entry.get("key") is None else "编辑辅助热键",
                 bg=T.BG_APP, fg=T.TEXT, font=self.fonts.title).pack(anchor="w", pady=(0, 14))

        # 触发键
        tk.Label(body, text="触发键", bg=T.BG_APP, fg=T.TEXT,
                 font=self.fonts.body).pack(anchor="w")
        tk.Label(body, text="点击下方键位区，然后按下你想用的按键。",
                 bg=T.BG_APP, fg=T.TEXT_MUTED, font=self.fonts.small).pack(anchor="w", pady=(2, 6))
        self._cap = KeyCapture(body, self.fonts, value=self._entry.get("key"))
        self._cap.pack(anchor="w", pady=(0, 14))

        # 标签
        tk.Label(body, text="描述（可选）", bg=T.BG_APP, fg=T.TEXT,
                 font=self.fonts.body).pack(anchor="w")
        tk.Label(body, text="自己看的标签，比如「录音并发送」。",
                 bg=T.BG_APP, fg=T.TEXT_MUTED, font=self.fonts.small).pack(anchor="w", pady=(2, 6))
        self._label_var = tk.StringVar(value=self._entry.get("label", ""))
        ent = tk.Entry(body, textvariable=self._label_var, font=self.fonts.body,
                       bg=T.N_0, fg=T.TEXT, relief="solid", bd=1,
                       highlightthickness=1, highlightbackground=T.BORDER_STRONG,
                       highlightcolor=T.ACCENT, insertbackground=T.TEXT)
        ent.configure(width=32)
        ent.pack(anchor="w", pady=(0, 14), ipady=4)

        # 主动作：paste 还是 clipboard（二选一）
        tk.Label(body, text="识别完成后", bg=T.BG_APP, fg=T.TEXT,
                 font=self.fonts.body).pack(anchor="w")
        self._primary_var = tk.StringVar()
        actions = self._entry.get("actions", ["paste"])
        if "paste" in actions:
            self._primary_var.set("paste")
        elif "clipboard" in actions:
            self._primary_var.set("clipboard")
        else:
            self._primary_var.set("paste")

        radio_row = tk.Frame(body, bg=T.BG_APP)
        radio_row.pack(anchor="w", pady=(6, 14))
        for val, text in [("paste", "粘贴到光标"), ("clipboard", "只复制到剪贴板")]:
            tk.Radiobutton(
                radio_row, text=text, variable=self._primary_var, value=val,
                bg=T.BG_APP, fg=T.TEXT, font=self.fonts.small,
                activebackground=T.BG_APP, selectcolor=T.N_0,
                highlightthickness=0,
            ).pack(side="left", padx=(0, 18))

        # 追加按键
        tk.Label(body, text="随后再按", bg=T.BG_APP, fg=T.TEXT,
                 font=self.fonts.body).pack(anchor="w")
        # 当前已有 press:xxx action
        current_press = ""
        for a in actions:
            if a.startswith("press:"):
                current_press = a[6:]
                break
        self._press_var = tk.StringVar(value=current_press)
        combo = tk.OptionMenu(body, self._press_var, *[v for v, _ in self.PRESS_OPTIONS])
        combo.configure(bg=T.N_0, fg=T.TEXT, font=self.fonts.small,
                        bd=1, relief="solid", highlightthickness=0,
                        activebackground=T.N_50, width=24)
        menu = combo["menu"]
        menu.delete(0, "end")
        for v, label in self.PRESS_OPTIONS:
            menu.add_command(label=label, command=lambda x=v: self._press_var.set(x))
        # Display 映射
        self._press_var.trace_add("write", lambda *a: self._update_combo_display(combo))
        self._update_combo_display(combo)
        combo.pack(anchor="w", pady=(6, 18))

        # 底部按钮
        btn_row = tk.Frame(body, bg=T.BG_APP)
        btn_row.pack(fill="x", pady=(10, 0))
        Button(btn_row, self.fonts, "取消",
               command=self.destroy, variant="ghost").pack(side="right")
        Button(btn_row, self.fonts, "保存",
               command=self._save, variant="primary").pack(side="right", padx=(0, 6))

    def _update_combo_display(self, combo):
        v = self._press_var.get()
        label = next((lab for val, lab in self.PRESS_OPTIONS if val == v), v)
        combo.configure(text=label)

    def _save(self):
        key = self._cap.get()
        if not key:
            self.shell_toast("触发键还没设置")
            return
        actions = [self._primary_var.get()]
        press = self._press_var.get().strip()
        if press:
            actions.append(f"press:{press}")
        self._entry["key"] = key
        self._entry["label"] = self._label_var.get().strip() or "Dictate"
        self._entry["actions"] = actions
        if self._on_save:
            self._on_save(self._entry)
        self.destroy()

    def shell_toast(self, msg):
        # 借父窗的 toast
        try:
            self.master.winfo_toplevel().toast(msg, tone="red")
        except Exception:
            pass
