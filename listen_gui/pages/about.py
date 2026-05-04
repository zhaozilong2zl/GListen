"""About 页 —— 版本、服务状态、凭证 / 存储位置、日志入口。"""
import platform
import subprocess
import sys
import tkinter as tk
from pathlib import Path

import config as vi_config
import history as vi_history
from .. import theme as T
from ..widgets import Section, Row, Pill, Button


CRED_PATH = Path.home() / ".config" / "doubao" / "credentials"
VOLCE_CONSOLE = "https://console.volcengine.com/speech/app"


def _fmt_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n/1024:.1f} KB"
    return f"{n/1024**2:.1f} MB"


def _xdg_open(path):
    """打开文件管理器到这个路径或跳到 URL。"""
    try:
        subprocess.Popen(["xdg-open", str(path)], start_new_session=True)
    except Exception:
        pass


def _ubuntu_release():
    """从 /etc/os-release 读发行版名称。拿不到就返回 platform.platform()。"""
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return platform.platform()


class AboutPage(tk.Frame):
    def __init__(self, parent, fonts, shell):
        super().__init__(parent, bg=T.BG_APP)
        self.fonts = fonts
        self.shell = shell

        self._build_header()
        self._build_service()
        self._build_storage()
        self._build_quota()
        self._build_system()

    # ---------- Header ----------
    def _build_header(self):
        card = tk.Frame(self, bg=T.BG_CARD, highlightthickness=1,
                        highlightbackground=T.BORDER)
        card.pack(fill="x", pady=(0, 12))

        inner = tk.Frame(card, bg=T.BG_CARD)
        inner.pack(fill="x", padx=22, pady=20)

        # 图标
        logo = tk.Canvas(inner, width=54, height=54, bg=T.BG_CARD,
                         highlightthickness=0)
        logo.pack(side="left", padx=(0, 16))
        # 圆角方块做不了（tk 限制），用普通矩形
        logo.create_rectangle(0, 0, 54, 54, fill=T.BLUE_600, outline="")
        # 波形状装饰
        for x1, y1, x2, y2 in [
            (10, 27, 16, 27),
            (19, 18, 25, 36),
            (28, 21, 34, 33),
            (37, 18, 43, 36),
            (46, 27, 54 - 4, 27),
        ]:
            logo.create_line(x1, y1, x2, y2, fill="white",
                             width=3, capstyle="round")

        right = tk.Frame(inner, bg=T.BG_CARD)
        right.pack(side="left", fill="x", expand=True)
        tk.Label(right, text="GListen 1.0.0", bg=T.BG_CARD, fg=T.TEXT,
                 font=self.fonts.title).pack(anchor="w")
        tk.Label(right,
                 text="Linux x11 语音输入 · 豆包流式 ASR 2.0 · 按住热键说话",
                 bg=T.BG_CARD, fg=T.TEXT_MUTED,
                 font=self.fonts.small).pack(anchor="w", pady=(4, 0))

    # ---------- Service ----------
    def _build_service(self):
        self._sec_service = Section(self, self.fonts, title="服务")
        self._sec_service.pack(fill="x", pady=(0, 12))

        row = tk.Frame(self._sec_service.body, bg=T.BG_CARD)
        row.pack(fill="x", padx=14, pady=10)

        left = tk.Frame(row, bg=T.BG_CARD)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="运行状态", bg=T.BG_CARD, fg=T.TEXT,
                 font=self.fonts.body, anchor="w").pack(anchor="w")
        tk.Label(left, text="voice-input.service (systemd --user)",
                 bg=T.BG_CARD, fg=T.TEXT_MUTED,
                 font=self.fonts.small, anchor="w",
                 wraplength=320).pack(anchor="w", pady=(2, 0))

        self._status_pill = Pill(row, self.fonts, "● 查询中…", tone="default")
        self._status_pill.pack(side="right")
        self._refresh_status()

        tk.Frame(self._sec_service.body, bg=T.BORDER, height=1).pack(fill="x")

        # 操作按钮 row
        op = tk.Frame(self._sec_service.body, bg=T.BG_CARD)
        op.pack(fill="x", padx=14, pady=12)
        Button(op, self.fonts, "重启服务",
               command=self._restart, variant="default").pack(side="left")
        Button(op, self.fonts, "停止",
               command=self._stop, variant="default"
               ).pack(side="left", padx=(6, 0))
        Button(op, self.fonts, "查看日志",
               command=self._show_logs, variant="default"
               ).pack(side="left", padx=(6, 0))
        Button(op, self.fonts, "刷新状态",
               command=self._refresh_status, variant="ghost"
               ).pack(side="right")

    def _refresh_status(self):
        from ..shell import query_service_status
        s = query_service_status()
        tone_map = {
            "active": ("green", "● Active"),
            "inactive": ("orange", "○ Stopped"),
            "failed": ("red", "● Failed"),
            "activating": ("blue", "● Starting"),
        }
        tone, text = tone_map.get(s, ("default", f"○ {s}"))
        self._status_pill.configure(text=text)
        self._status_pill.set_tone(tone)

    def _restart(self):
        from ..shell import restart_service
        ok, msg = restart_service()
        self.shell.toast(f"已重启" if ok else f"重启失败: {msg}",
                         tone="green" if ok else "red")
        self.after(500, self._refresh_status)

    def _stop(self):
        try:
            r = subprocess.run(
                ["systemctl", "--user", "stop", "voice-input"],
                capture_output=True, text=True, timeout=6,
            )
            if r.returncode == 0:
                self.shell.toast("已停止")
            else:
                self.shell.toast(f"失败: {r.stderr.strip()[:80]}", tone="red")
        except Exception as e:
            self.shell.toast(f"失败: {e}", tone="red")
        self.after(300, self._refresh_status)

    def _show_logs(self):
        LogViewer(self, self.fonts)

    # ---------- Storage ----------
    def _build_storage(self):
        self._sec_store = Section(self, self.fonts, title="存储与凭证")
        self._sec_store.pack(fill="x", pady=(0, 12))

        # 凭证
        self._kv_row("豆包凭证",
                     subtitle=str(CRED_PATH),
                     right_builder=lambda row: Button(
                         row, self.fonts,
                         "存在" if CRED_PATH.exists() else "不存在",
                         command=lambda: _xdg_open(CRED_PATH.parent),
                         variant="default" if CRED_PATH.exists() else "danger",
                     ))

        # 历史 DB
        db_path = vi_history._db_path()
        db_size = db_path.stat().st_size if db_path.exists() else 0
        self._kv_row("历史数据库",
                     subtitle=f"{db_path}\n{_fmt_size(db_size)}",
                     right_builder=lambda row: Button(
                         row, self.fonts, "打开目录",
                         command=lambda: _xdg_open(db_path.parent),
                         variant="default"))

        # 配置
        cfg_path = vi_config.config_path()
        self._kv_row("配置文件",
                     subtitle=str(cfg_path),
                     right_builder=lambda row: Button(
                         row, self.fonts, "打开目录",
                         command=lambda: _xdg_open(cfg_path.parent),
                         variant="default"),
                     last=True)

    def _kv_row(self, title, subtitle, right_builder=None, last=False):
        """两行布局的 Row：标题 + 多行 subtitle + 右侧按钮。"""
        row = tk.Frame(self._sec_store.body, bg=T.BG_CARD)
        row.pack(fill="x", padx=14, pady=10)
        left = tk.Frame(row, bg=T.BG_CARD)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=title, bg=T.BG_CARD, fg=T.TEXT,
                 font=self.fonts.body, anchor="w").pack(anchor="w")
        tk.Label(left, text=subtitle, bg=T.BG_CARD, fg=T.TEXT_MUTED,
                 font=self.fonts.small, anchor="w", justify="left",
                 wraplength=360).pack(anchor="w", pady=(2, 0))
        if right_builder:
            btn = right_builder(row)
            btn.pack(side="right")
        if not last:
            tk.Frame(self._sec_store.body, bg=T.BORDER, height=1).pack(fill="x")

    # ---------- Quota ----------
    def _build_quota(self):
        sec = Section(self, self.fonts, title="豆包额度")
        sec.pack(fill="x", pady=(0, 12))

        row = tk.Frame(sec.body, bg=T.BG_CARD)
        row.pack(fill="x", padx=14, pady=12)
        left = tk.Frame(row, bg=T.BG_CARD)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="剩余额度", bg=T.BG_CARD, fg=T.TEXT,
                 font=self.fonts.body, anchor="w").pack(anchor="w")
        tk.Label(left,
                 text="豆包没提供程序化查询接口。去火山控制台看实时用量。",
                 bg=T.BG_CARD, fg=T.TEXT_MUTED, font=self.fonts.small,
                 wraplength=360, anchor="w",
                 justify="left").pack(anchor="w", pady=(2, 0))
        Button(row, self.fonts, "打开控制台 ↗",
               command=lambda: _xdg_open(VOLCE_CONSOLE),
               variant="default").pack(side="right")

    # ---------- System ----------
    def _build_system(self):
        sec = Section(self, self.fonts, title="系统")
        sec.pack(fill="x", pady=(0, 12))
        items = [
            ("平台", _ubuntu_release()),
            ("Daemon Python",
             f"Anaconda {sys.version_info.major}.{sys.version_info.minor}"),
            ("GUI Python", "/usr/bin/python3 (系统 Xft 支持)"),
            ("tk 版本", f"{tk.TkVersion}"),
            ("项目路径", str(Path(__file__).resolve().parent.parent.parent)),
        ]
        for i, (k, v) in enumerate(items):
            row = tk.Frame(sec.body, bg=T.BG_CARD)
            row.pack(fill="x", padx=14, pady=8)
            tk.Label(row, text=k, bg=T.BG_CARD, fg=T.TEXT_MUTED,
                     font=self.fonts.small, width=14, anchor="w"
                     ).pack(side="left")
            tk.Label(row, text=v, bg=T.BG_CARD, fg=T.TEXT,
                     font=self.fonts.small, anchor="w",
                     wraplength=420, justify="left"
                     ).pack(side="left", fill="x", expand=True)
            if i < len(items) - 1:
                tk.Frame(sec.body, bg=T.BORDER, height=1).pack(fill="x")


class LogViewer(tk.Toplevel):
    """journalctl 日志弹窗。只读 Text。"""

    def __init__(self, parent, fonts):
        super().__init__(parent)
        self.title("GListen — 日志 (最近 200 行)")
        self.geometry("800x520")
        self.configure(bg=T.BG_APP)
        self.transient(parent.winfo_toplevel())
        try:
            self.grab_set()
        except Exception:
            pass
        self.bind("<Escape>", lambda _e: self.destroy())

        # 顶部工具条
        top = tk.Frame(self, bg=T.BG_APP)
        top.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(top, text="journalctl --user -u voice-input -n 200",
                 bg=T.BG_APP, fg=T.TEXT_MUTED, font=fonts.mono
                 ).pack(side="left")
        Button(top, fonts, "刷新", command=self._reload,
               variant="ghost").pack(side="right")
        Button(top, fonts, "关闭", command=self.destroy,
               variant="default").pack(side="right", padx=(0, 6))

        # 文本区
        wrap = tk.Frame(self, bg=T.BG_APP)
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._text = tk.Text(
            wrap, bg="#0f1115", fg="#d8dce3", font=fonts.mono,
            insertbackground="#d8dce3", relief="flat", bd=0,
            highlightthickness=1, highlightbackground=T.BORDER,
            wrap="none", padx=10, pady=10,
        )
        self._text.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self._text.yview)
        sb.pack(side="right", fill="y")
        self._text.configure(yscrollcommand=sb.set)
        # 横向滚动
        self._reload()

    def _reload(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        try:
            r = subprocess.run(
                ["journalctl", "--user", "-u", "voice-input",
                 "-n", "200", "--no-pager"],
                capture_output=True, text=True, timeout=5,
            )
            out = r.stdout or r.stderr or "(no output)"
        except Exception as e:
            out = f"读取日志失败: {e}"
        self._text.insert("1.0", out)
        self._text.see("end")
        self._text.configure(state="disabled")
