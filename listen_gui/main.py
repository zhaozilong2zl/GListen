#!/usr/bin/env python3
"""
Listen 设置窗入口。

必须用系统 /usr/bin/python3 跑 —— anaconda 的 libtk 没链 libXft/libfontconfig，
中文字体会 fallback 成方块。cli.py 的 `glisten config` 子命令负责用对的解释器启动。
"""
import sys
from pathlib import Path

# 让 listen_gui 能 import 顶层的 config / history / keys 模块
_PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ))

from listen_gui.shell import Shell, query_service_status  # noqa: E402
from listen_gui.pages.shortcuts import ShortcutsPage      # noqa: E402
from listen_gui.pages.behavior import BehaviorPage        # noqa: E402
from listen_gui.pages.postprocess import PostprocessPage  # noqa: E402
from listen_gui.pages.history import HistoryPage          # noqa: E402
from listen_gui.pages.about import AboutPage              # noqa: E402


NAV = [
    {
        "label": "Input",
        "items": [
            {"id": "shortcuts",   "label": "快捷键", "icon": "⌨"},
            {"id": "behavior",    "label": "行为",   "icon": "⚙"},
            {"id": "postprocess", "label": "后处理", "icon": "Ξ"},
        ],
    },
    {
        "label": "Data",
        "items": [
            {"id": "history",     "label": "历史",   "icon": "⏱"},
        ],
    },
    {
        "label": "App",
        "items": [
            {"id": "about",       "label": "关于",   "icon": "ⓘ"},
        ],
    },
]


def refresh_status(shell):
    """每 3s 轮询一次服务状态，更新底部 Pill。"""
    s = query_service_status()
    if s == "active":
        shell.set_status("● Active", "green")
    elif s == "inactive":
        shell.set_status("○ Stopped", "orange")
    elif s == "failed":
        shell.set_status("● Failed", "red")
    elif s == "activating":
        shell.set_status("● Starting…", "blue")
    else:
        shell.set_status("○ Unknown", "default")
    shell.after(3000, lambda: refresh_status(shell))


def main():
    shell = Shell(nav_groups=NAV)
    shell.add_page(
        "shortcuts", "快捷键",
        "主键按住录音、松开粘贴；可以再添加辅助键绑定不同动作。",
        ShortcutsPage(shell._body, shell.fonts, shell),
    )
    shell.add_page(
        "behavior", "行为",
        "输入方式、粘贴快捷键、悬浮框等。",
        BehaviorPage(shell._body, shell.fonts, shell),
    )
    shell.add_page(
        "postprocess", "后处理",
        "把口语替换成符号或专有名词（「点」→「.」、「克劳德」→「Claude」）。",
        PostprocessPage(shell._body, shell.fonts, shell),
    )
    shell.add_page(
        "history", "历史",
        "最近的识别记录，按时间降序。",
        HistoryPage(shell._body, shell.fonts, shell),
    )
    shell.add_page(
        "about", "关于",
        "版本、服务状态、凭证 / 存储位置、日志。",
        AboutPage(shell._body, shell.fonts, shell),
    )
    refresh_status(shell)
    shell.mainloop()


if __name__ == "__main__":
    main()
