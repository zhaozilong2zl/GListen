"""
窗口骨架：Titlebar + Sidebar + Main + Status。

不做真正的 frameless window（overrideredirect 会丢 WM 功能如 Super+鼠标拖动、Ctrl+Alt+←/→ 切工作区等）——用标准 Toplevel，标题栏交给 WM。
"""
import subprocess
import tkinter as tk
from typing import Callable, Dict, List, Optional

from . import theme as T
from .widgets import Pill


class Shell(tk.Tk):
    """主窗口。调用 add_page 注册页面，select_page 切换显示。"""

    def __init__(self, nav_groups: List[dict], on_page_change: Optional[Callable] = None):
        super().__init__()
        self.title("GListen — Preferences")
        self.geometry(f"{T.WIN_W}x{T.WIN_H}")
        self.minsize(T.WIN_W, T.WIN_H)
        self.configure(bg=T.BG_APP)

        from .theme import Fonts
        self.fonts = Fonts(self)

        self._pages: Dict[str, tk.Frame] = {}
        self._active_page: Optional[str] = None
        self._on_page_change = on_page_change
        self._nav_buttons: Dict[str, tk.Button] = {}
        self._nav_badges: Dict[str, tk.Label] = {}

        root = tk.Frame(self, bg=T.BG_APP)
        root.pack(fill="both", expand=True)

        self._build_sidebar(root, nav_groups)

        # 主区
        self._main = tk.Frame(root, bg=T.BG_APP)
        self._main.pack(side="left", fill="both", expand=True)
        self._page_head = tk.Frame(self._main, bg=T.BG_APP, height=72)
        self._page_head.pack(fill="x")
        self._page_head.pack_propagate(False)
        self._head_title = tk.Label(
            self._page_head, text="", bg=T.BG_APP, fg=T.TEXT,
            font=self.fonts.title, anchor="w",
        )
        self._head_title.pack(side="left", fill="x", expand=True, padx=28, pady=(22, 4))
        self._head_sub = tk.Label(
            self._page_head, text="", bg=T.BG_APP, fg=T.TEXT_MUTED,
            font=self.fonts.small,
        )
        # 副标题用的时候再 pack

        tk.Frame(self._main, bg=T.BORDER, height=1).pack(fill="x")

        # page body：Canvas + Scrollbar 让内容超过窗口高度时能滚动
        body_outer = tk.Frame(self._main, bg=T.BG_APP)
        body_outer.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(body_outer, bg=T.BG_APP, highlightthickness=0)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scroll = tk.Scrollbar(body_outer, orient="vertical",
                                    command=self._canvas.yview,
                                    bg=T.BG_APP, troughcolor=T.N_75,
                                    activebackground=T.N_200, borderwidth=0,
                                    width=10, elementborderwidth=0)
        self._scroll.pack(side="right", fill="y")
        self._canvas.configure(yscrollcommand=self._scroll.set)
        # 真正挂 page 的 frame，嵌在 Canvas 里
        self._body = tk.Frame(self._canvas, bg=T.BG_APP)
        self._body_window_id = self._canvas.create_window(
            (0, 0), window=self._body, anchor="nw",
        )
        # 滚动区域随内容自适应；Canvas 宽度变化时同步 _body 宽度
        def _on_body_configure(_e):
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        def _on_canvas_configure(e):
            self._canvas.itemconfigure(self._body_window_id, width=e.width)
        self._body.bind("<Configure>", _on_body_configure)
        self._canvas.bind("<Configure>", _on_canvas_configure)
        # 鼠标滚轮（Linux 是 Button-4/5，不是 <MouseWheel>）
        def _on_wheel(e):
            delta = -1 if e.num == 4 else 1
            self._canvas.yview_scroll(delta * 2, "units")
        self._canvas.bind_all("<Button-4>", _on_wheel)
        self._canvas.bind_all("<Button-5>", _on_wheel)

    # ---------- Sidebar ----------
    def _build_sidebar(self, parent, nav_groups):
        sidebar = tk.Frame(parent, bg=T.BG_SIDEBAR, width=210,
                           highlightthickness=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Brand
        brand = tk.Frame(sidebar, bg=T.BG_SIDEBAR)
        brand.pack(fill="x", padx=14, pady=(18, 14))
        # 用 Canvas 画一个渐变感方块图标
        logo = tk.Canvas(brand, width=26, height=26, bg=T.BG_SIDEBAR,
                         highlightthickness=0)
        logo.pack(side="left")
        logo.create_rectangle(0, 0, 26, 26, fill=T.BLUE_600, outline="")
        # 三条"波形"白线表意
        for i, (x1, y1, x2, y2) in enumerate([
            (6, 13, 9, 13),
            (11, 9, 14, 17),
            (16, 11, 19, 15),
            (21, 13, 24, 13),
        ]):
            logo.create_line(x1, y1, x2, y2, fill="white", width=2, capstyle="round")
        tk.Label(brand, text="GListen", bg=T.BG_SIDEBAR, fg=T.TEXT,
                 font=self.fonts.heading).pack(side="left", padx=(10, 0))
        tk.Label(brand, text="1.0.0", bg=T.N_100, fg=T.TEXT_SUBTLE,
                 font=self.fonts.tiny, padx=6, pady=1).pack(side="right")

        # Nav items
        for group in nav_groups:
            tk.Label(sidebar, text=group["label"].upper(),
                     bg=T.BG_SIDEBAR, fg=T.TEXT_SUBTLE,
                     font=self.fonts.tiny, anchor="w"
                     ).pack(fill="x", padx=18, pady=(10, 2))
            for item in group["items"]:
                self._build_nav_item(sidebar, item)

        # Status footer（底部服务状态）
        tk.Frame(sidebar, bg=T.BORDER, height=1).pack(fill="x", side="bottom", pady=(0, 0))
        self._status_frame = tk.Frame(sidebar, bg=T.BG_SIDEBAR)
        self._status_frame.pack(side="bottom", fill="x", padx=10, pady=10)
        self._status_pill = Pill(self._status_frame, self.fonts, "●  ?", tone="default")
        self._status_pill.pack(side="left")
        self._status_extra = tk.Label(self._status_frame, text="",
                                      bg=T.BG_SIDEBAR, fg=T.TEXT_SUBTLE,
                                      font=self.fonts.tiny)
        self._status_extra.pack(side="right")

    def _build_nav_item(self, parent, item):
        frame = tk.Frame(parent, bg=T.BG_SIDEBAR)
        frame.pack(fill="x", padx=8, pady=1)

        btn = tk.Button(
            frame, text=f"  {item['icon']}  {item['label']}",
            anchor="w", relief="flat", borderwidth=0, highlightthickness=0,
            bg=T.BG_SIDEBAR, fg=T.N_700, font=self.fonts.small,
            activebackground=T.N_100, activeforeground=T.N_700,
            padx=10, pady=6, cursor="hand2",
            command=lambda pid=item["id"]: self.select_page(pid),
        )
        btn.pack(side="left", fill="x", expand=True)
        self._nav_buttons[item["id"]] = btn

        # 可选 badge
        badge = tk.Label(frame, text="", bg=T.BG_SIDEBAR, fg=T.TEXT_MUTED,
                         font=self.fonts.tiny, padx=6, pady=1)
        badge.pack(side="right", padx=(0, 4))
        self._nav_badges[item["id"]] = badge

    # ---------- API ----------
    def add_page(self, page_id: str, title: str, subtitle: str, page: tk.Frame):
        """注册一个页面。page 是一个 Frame，会被 pack 到 body。
        title/subtitle 用于顶部 page-head 显示。
        """
        page._meta = {"title": title, "subtitle": subtitle}
        self._pages[page_id] = page
        # 先不 pack，select_page 时再 pack
        if self._active_page is None:
            self.select_page(page_id)

    def select_page(self, page_id: str):
        if page_id not in self._pages:
            return
        # 隐藏旧 page
        if self._active_page and self._active_page in self._pages:
            self._pages[self._active_page].pack_forget()
        # 更新 head
        meta = self._pages[page_id]._meta
        self._head_title.configure(text=meta["title"])
        if meta["subtitle"]:
            self._head_sub.configure(text=meta["subtitle"])
            self._head_sub.pack(side="left", padx=(0, 28), pady=(0, 22))
        else:
            self._head_sub.pack_forget()
        # 显示新 page
        self._pages[page_id].pack(fill="both", expand=True, padx=24, pady=(16, 16))
        # 更新 nav 高亮
        for pid, btn in self._nav_buttons.items():
            if pid == page_id:
                btn.configure(bg=T.N_0, fg=T.ACCENT,
                              activebackground=T.N_0, activeforeground=T.ACCENT)
                self._nav_badges[pid].configure(bg=T.PILL_BLUE_BG, fg=T.PILL_BLUE_FG)
            else:
                btn.configure(bg=T.BG_SIDEBAR, fg=T.N_700,
                              activebackground=T.N_100, activeforeground=T.N_700)
                self._nav_badges[pid].configure(bg=T.BG_SIDEBAR, fg=T.TEXT_MUTED)
        self._active_page = page_id
        if self._on_page_change:
            self._on_page_change(page_id)

    def set_nav_badge(self, page_id: str, text: str):
        if page_id in self._nav_badges:
            self._nav_badges[page_id].configure(text=text)

    def set_status(self, pill_text: str, pill_tone: str, extra: str = ""):
        self._status_pill.configure(text=pill_text)
        self._status_pill.set_tone(pill_tone)
        self._status_extra.configure(text=extra)

    # ---------- 保存配置 + 重启服务 ----------
    def apply_changes(self, config_dict: dict, restart: bool = True):
        """写 config.json；可选重启 glisten。顶部闪一个 toast。"""
        import config as vi_config  # 顶层模块
        try:
            vi_config.save(config_dict)
        except Exception as e:
            self.toast(f"保存失败: {e}", tone="red")
            return
        if not restart:
            self.toast("已保存")
            return
        ok, msg = restart_service()
        if ok:
            self.toast("已保存并重启服务")
        else:
            self.toast(f"已保存，但重启失败: {msg}", tone="red")

    def toast(self, message: str, tone: str = "default", duration_ms: int = 1800):
        """在窗口底部中央浮一个 Pill，到时间自动消失。"""
        if getattr(self, "_toast", None) is not None:
            try:
                self._toast.destroy()
            except Exception:
                pass
        t = Pill(self._main, self.fonts, message, tone=tone)
        t.configure(padx=12, pady=6, font=self.fonts.small)
        t.place(relx=0.5, rely=1.0, anchor="s", y=-16)
        self._toast = t
        self.after(duration_ms, lambda tw=t: tw.destroy() if tw.winfo_exists() else None)


# ---------- 服务状态查询（systemctl --user）----------
def query_service_status() -> str:
    """返回 'active' / 'inactive' / 'failed' / 'unknown'。"""
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", "glisten"],
            capture_output=True, text=True, timeout=2,
        )
        s = r.stdout.strip()
        if s in ("active", "inactive", "failed", "activating", "deactivating"):
            return s
    except Exception:
        pass
    return "unknown"


def restart_service() -> tuple:
    """重启 glisten 服务。返回 (success: bool, msg: str)。"""
    try:
        r = subprocess.run(
            ["systemctl", "--user", "restart", "glisten"],
            capture_output=True, text=True, timeout=6,
        )
        if r.returncode == 0:
            return True, "已重启"
        return False, r.stderr.strip() or "未知错误"
    except Exception as e:
        return False, str(e)
