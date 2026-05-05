"""后处理规则编辑页。

规则以 config.postprocess.rules 存储。每条 = {pattern, replacement, boundary, enabled}
- boundary: word   两侧必须都是 [A-Za-z0-9_]+ 才替换（避免误伤「重点」「观点」）
-           always 任何位置都替换（适合纯文本替换，如「克劳德」→「Claude」）
"""
import tkinter as tk
from copy import deepcopy

import config as vi_config
from .. import theme as T
from ..widgets import Section, Pill, Button


BOUNDARY_OPTIONS = [
    ("word",   "仅代码边界"),
    ("always", "任何位置"),
]


class PostprocessPage(tk.Frame):
    def __init__(self, parent, fonts, shell):
        super().__init__(parent, bg=T.BG_APP)
        self.fonts = fonts
        self.shell = shell
        self._cfg = vi_config.load()
        self._rules = self._cfg.setdefault(
            "postprocess", {"rules": []}
        ).setdefault("rules", [])

        self._build_intro()
        self._build_rules_section()
        self._build_builtin_section()

    def _build_intro(self):
        card = tk.Frame(self, bg=T.BG_CARD, highlightthickness=1,
                        highlightbackground=T.BORDER)
        card.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(card, bg=T.BG_CARD)
        inner.pack(fill="x", padx=22, pady=18)

        tk.Label(inner, text="后处理规则",
                 bg=T.BG_CARD, fg=T.TEXT,
                 font=self.fonts.title, anchor="w"
                 ).pack(anchor="w")

        tk.Label(
            inner,
            text=('识别结果送到光标前会先过一遍你定义的替换规则。'
                  '比如说「settings 点 json」，规则「点→.」把它变成「settings.json」。\n\n'
                  '两种边界模式：\n'
                  '• 仅代码边界（推荐做符号类）：两侧都是英文/数字/下划线才触发。'
                  '这样「重点」「观点」里的「点」不会被误改为 "."\n'
                  '• 任何位置（适合专有名词）：只要文本里出现就替换。'
                  '例如「克劳德」→「Claude」、「派森」→「Python」'),
            bg=T.BG_CARD, fg=T.TEXT_MUTED,
            font=self.fonts.small, anchor="w", justify="left",
            wraplength=560,
        ).pack(anchor="w", pady=(8, 0))

    def _build_rules_section(self):
        self._sec = Section(self, self.fonts, title="自定义规则")
        self._sec.pack(fill="x", pady=(0, 12))
        Button(self._sec.header, self.fonts, "＋ 添加",
               command=self._add_rule, variant="header"
               ).pack(side="right", padx=10, pady=6)
        self._list = self._sec.body
        self._render_rules()

    def _render_rules(self):
        for w in self._list.winfo_children():
            w.destroy()
        if not self._rules:
            tk.Label(
                self._list,
                text="（没有规则。点右上角「＋ 添加」加一条，例如「点」→「.」）",
                bg=T.BG_CARD, fg=T.TEXT_SUBTLE, font=self.fonts.small,
                anchor="w", justify="left", wraplength=560,
                padx=14, pady=14,
            ).pack(anchor="w")
            return
        for i, rule in enumerate(self._rules):
            self._render_row(rule, i, last=(i == len(self._rules) - 1))

    def _render_row(self, rule, index, last=False):
        row = tk.Frame(self._list, bg=T.BG_CARD)
        row.pack(fill="x", padx=14, pady=10)

        # 右：编辑 / 删除
        right = tk.Frame(row, bg=T.BG_CARD)
        right.pack(side="right")
        Button(right, self.fonts, "编辑",
               command=lambda i=index: self._edit_rule(i),
               variant="ghost").pack(side="left", padx=(0, 4))
        Button(right, self.fonts, "删除",
               command=lambda i=index: self._delete_rule(i),
               variant="danger").pack(side="left")

        # 左：开关
        sw = EnabledToggle(row, initial=rule.get("enabled", True),
                           on_change=lambda v, i=index: self._toggle_rule(i, v))
        sw.pack(side="left", padx=(0, 10))

        # 中：pattern → replacement + boundary Pill
        mid = tk.Frame(row, bg=T.BG_CARD)
        mid.pack(side="left", fill="x", expand=True)

        first_line = tk.Frame(mid, bg=T.BG_CARD)
        first_line.pack(anchor="w", fill="x")

        pat = rule.get("pattern", "") or "(空)"
        rep = rule.get("replacement", "")
        rep_show = f'"{rep}"' if rep else "(空)"

        tk.Label(first_line, text=pat, bg=T.BG_CARD, fg=T.TEXT,
                 font=self.fonts.body).pack(side="left")
        tk.Label(first_line, text="  →  ", bg=T.BG_CARD, fg=T.TEXT_SUBTLE,
                 font=self.fonts.body).pack(side="left")
        tk.Label(first_line, text=rep_show, bg=T.BG_CARD, fg=T.TEXT,
                 font=self.fonts.mono).pack(side="left")

        boundary = rule.get("boundary", "word")
        tone = "blue" if boundary == "word" else "orange"
        label = "仅代码边界" if boundary == "word" else "任何位置"
        Pill(mid, self.fonts, label, tone=tone).pack(anchor="w", pady=(4, 0))

        if not last:
            tk.Frame(self._list, bg=T.BORDER, height=1).pack(fill="x", padx=14)

    def _add_rule(self):
        RuleDialog(self, self.fonts, rule=None, on_save=self._save_new)

    def _edit_rule(self, index):
        RuleDialog(self, self.fonts, rule=deepcopy(self._rules[index]),
                   on_save=lambda r: self._save_edit(index, r))

    def _save_new(self, new_rule):
        self._rules.append(new_rule)
        self._apply()
        self._render_rules()

    def _save_edit(self, index, new_rule):
        self._rules[index] = new_rule
        self._apply()
        self._render_rules()

    def _delete_rule(self, index):
        del self._rules[index]
        self._apply()
        self._render_rules()

    def _toggle_rule(self, index, enabled):
        self._rules[index]["enabled"] = enabled
        self._apply()
        # 不 re-render（切换开关就不重绘，体感更顺）

    def _apply(self):
        cfg = vi_config.load()
        cfg.setdefault("postprocess", {})["rules"] = self._rules
        self.shell.apply_changes(cfg, restart=True)

    # ---------- 内置规则（只读展示）----------
    def _build_builtin_section(self):
        sec = Section(self, self.fonts, title="内置处理（不可编辑）")
        sec.pack(fill="x", pady=(0, 12))

        items = [
            ("连续单字母合并",
             '"m a i n" → "main"；用户一个字母一个字母念不熟的单词时 ASR 会带空格。'),
            ("路径/扩展名短大写转小写",
             '"SRC/" → "src/"、".PY" → ".py"。ASR 对 2-5 字符短词倾向大写化，'
             '在路径或扩展名位置自动修正。'),
        ]
        for i, (title, desc) in enumerate(items):
            row = tk.Frame(sec.body, bg=T.BG_CARD)
            row.pack(fill="x", padx=14, pady=10)
            tk.Label(row, text=title, bg=T.BG_CARD, fg=T.TEXT,
                     font=self.fonts.body, anchor="w"
                     ).pack(anchor="w")
            tk.Label(row, text=desc, bg=T.BG_CARD, fg=T.TEXT_MUTED,
                     font=self.fonts.small, anchor="w",
                     justify="left", wraplength=560
                     ).pack(anchor="w", pady=(2, 0))
            if i < len(items) - 1:
                tk.Frame(sec.body, bg=T.BORDER, height=1).pack(fill="x", padx=14)


class EnabledToggle(tk.Canvas):
    """紧凑的圆形开关 —— 比 Switch 小，放行首。"""

    def __init__(self, parent, initial=True, on_change=None):
        super().__init__(parent, width=16, height=16, bg=T.BG_CARD,
                         highlightthickness=0, cursor="hand2")
        self._value = bool(initial)
        self._on_change = on_change
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _draw(self):
        self.delete("all")
        if self._value:
            self.create_oval(1, 1, 15, 15, fill=T.ACCENT, outline="")
            # 勾
            self.create_line(4, 8, 7, 11, 12, 5,
                             fill="white", width=2, capstyle="round")
        else:
            self.create_oval(1, 1, 15, 15, fill=T.N_0,
                             outline=T.BORDER_STRONG, width=1.2)

    def _toggle(self, _e):
        self._value = not self._value
        self._draw()
        if self._on_change:
            self._on_change(self._value)


class RuleDialog(tk.Toplevel):
    """添加/编辑规则。"""

    def __init__(self, parent, fonts, rule=None, on_save=None):
        super().__init__(parent)
        self.fonts = fonts
        self._on_save = on_save
        self._rule = rule or {
            "pattern": "", "replacement": "",
            "boundary": "word", "enabled": True,
        }
        self.title("后处理规则")
        self.configure(bg=T.BG_APP)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        try:
            self.grab_set()
        except Exception:
            pass
        self.bind("<Escape>", lambda _e: self.destroy())

        self._build()
        self.update_idletasks()
        p = parent.winfo_toplevel()
        x = p.winfo_rootx() + (p.winfo_width() - self.winfo_width()) // 2
        y = p.winfo_rooty() + (p.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _build(self):
        body = tk.Frame(self, bg=T.BG_APP)
        body.pack(fill="both", expand=True, padx=22, pady=20)

        is_edit = bool(self._rule.get("pattern"))
        tk.Label(body, text="编辑规则" if is_edit else "添加规则",
                 bg=T.BG_APP, fg=T.TEXT, font=self.fonts.title
                 ).pack(anchor="w", pady=(0, 14))

        # pattern
        tk.Label(body, text="口语（要替换的文本）",
                 bg=T.BG_APP, fg=T.TEXT, font=self.fonts.body
                 ).pack(anchor="w")
        tk.Label(body, text='比如「点」「斜杠」「克劳德」',
                 bg=T.BG_APP, fg=T.TEXT_MUTED, font=self.fonts.small
                 ).pack(anchor="w", pady=(2, 4))
        self._pat_var = tk.StringVar(value=self._rule.get("pattern", ""))
        self._mk_entry(body, self._pat_var, width=36).pack(
            anchor="w", pady=(0, 14), ipady=4)

        # replacement
        tk.Label(body, text="替换为",
                 bg=T.BG_APP, fg=T.TEXT, font=self.fonts.body
                 ).pack(anchor="w")
        tk.Label(body, text='符号或名词，比如 . / _ Claude Python',
                 bg=T.BG_APP, fg=T.TEXT_MUTED, font=self.fonts.small
                 ).pack(anchor="w", pady=(2, 4))
        self._rep_var = tk.StringVar(value=self._rule.get("replacement", ""))
        self._mk_entry(body, self._rep_var, width=36).pack(
            anchor="w", pady=(0, 14), ipady=4)

        # boundary
        tk.Label(body, text="匹配边界",
                 bg=T.BG_APP, fg=T.TEXT, font=self.fonts.body
                 ).pack(anchor="w")
        tk.Label(
            body,
            text=('• 仅代码边界：两侧必须有英文/数字/下划线才触发。'
                  '适合做符号类（避免「重点」误改）\n'
                  '• 任何位置：只要出现就替换。适合专有名词'),
            bg=T.BG_APP, fg=T.TEXT_MUTED, font=self.fonts.small,
            justify="left", wraplength=380,
        ).pack(anchor="w", pady=(2, 6))
        self._boundary_var = tk.StringVar(
            value=self._rule.get("boundary", "word"))
        radio_row = tk.Frame(body, bg=T.BG_APP)
        radio_row.pack(anchor="w", pady=(0, 18))
        for val, label in BOUNDARY_OPTIONS:
            tk.Radiobutton(
                radio_row, text=label, variable=self._boundary_var, value=val,
                bg=T.BG_APP, fg=T.TEXT, font=self.fonts.small,
                activebackground=T.BG_APP, selectcolor=T.N_0,
                highlightthickness=0,
            ).pack(side="left", padx=(0, 18))

        # 按钮
        btn_row = tk.Frame(body, bg=T.BG_APP)
        btn_row.pack(fill="x", pady=(10, 0))
        Button(btn_row, self.fonts, "取消",
               command=self.destroy, variant="ghost").pack(side="right")
        Button(btn_row, self.fonts, "保存",
               command=self._save, variant="primary"
               ).pack(side="right", padx=(0, 6))

    def _mk_entry(self, parent, var, width=36):
        return tk.Entry(
            parent, textvariable=var, font=self.fonts.body, width=width,
            bg=T.N_0, fg=T.TEXT, relief="solid", bd=1,
            highlightthickness=1, highlightbackground=T.BORDER_STRONG,
            highlightcolor=T.ACCENT, insertbackground=T.TEXT,
        )

    def _save(self):
        pat = self._pat_var.get().strip()
        if not pat:
            try:
                self.master.winfo_toplevel().toast("口语不能为空", tone="red")
            except Exception:
                pass
            return
        self._rule["pattern"] = pat
        self._rule["replacement"] = self._rep_var.get()  # 允许替换为空（删词）
        self._rule["boundary"] = self._boundary_var.get()
        self._rule["enabled"] = self._rule.get("enabled", True)
        if self._on_save:
            self._on_save(self._rule)
        self.destroy()
