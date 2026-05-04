"""
Listen 设计 token。对标 Claude Design 稿里的 CSS --n-xx / --blue-xx。
颜色都是 hex，tkinter 直接用。尺寸单位是像素。

浅色主题，蓝色 accent —— 和 Claude Design 给的视觉一致。
悬浮框（overlay_gui.py）是深色 HUD 风格，跟主窗是两回事，不共享这套 token。
"""
import tkinter.font as tkfont


# Blues
BLUE_50  = "#eff6ff"
BLUE_100 = "#dbeafe"
BLUE_200 = "#bfdbfe"
BLUE_400 = "#60a5fa"
BLUE_500 = "#3b82f6"
BLUE_600 = "#2563eb"
BLUE_700 = "#1d4ed8"

# Neutrals（n-0 = 白，n-900 = 近黑）
N_0   = "#ffffff"
N_25  = "#fbfcfd"
N_50  = "#f6f7f9"
N_75  = "#eff1f4"
N_100 = "#e6e9ee"
N_150 = "#d8dce3"
N_200 = "#c6ccd5"
N_300 = "#a8b0bc"
N_400 = "#828a98"
N_500 = "#616875"
N_600 = "#464c57"
N_700 = "#2f343c"
N_800 = "#1d2026"
N_900 = "#0f1115"

# Semantics
SUCCESS = "#16a34a"
WARNING = "#d97706"
DANGER  = "#dc2626"

# Surface
BG_APP      = N_50
BG_SIDEBAR  = N_75
BG_CARD     = N_0
BG_TITLEBAR = N_75
BG_INSET    = N_50
BG_ACCENT_SOFT = BLUE_50

BORDER        = N_100
BORDER_STRONG = N_150
TEXT          = N_800
TEXT_MUTED    = N_500
TEXT_SUBTLE   = N_400
ACCENT        = BLUE_600

# Pill tones
PILL_DEFAULT_BG = N_100
PILL_DEFAULT_FG = TEXT_MUTED
PILL_BLUE_BG    = BLUE_50
PILL_BLUE_FG    = BLUE_600
PILL_GREEN_BG   = "#dcfce7"
PILL_GREEN_FG   = "#166534"
PILL_ORANGE_BG  = "#ffedd5"
PILL_ORANGE_FG  = "#9a3412"
PILL_RED_BG     = "#fee2e2"
PILL_RED_FG     = "#991b1b"

# Window
WIN_W = 760
WIN_H = 560

# CJK 字体候选（和 overlay_gui.py 一样的列表）
CJK_CANDIDATES = (
    "Noto Sans CJK SC",
    "Source Han Sans CN",
    "WenQuanYi Micro Hei",
    "Sarasa Gothic SC",
    "DejaVu Sans",
)


def pick_font_family(root) -> str:
    """运行在 Tk root 上下文下选 CJK 字体。和 overlay_gui.py 同逻辑。"""
    available = set(tkfont.families(root=root))
    for f in CJK_CANDIDATES:
        if f in available:
            return f
    return tkfont.nametofont("TkDefaultFont").actual("family")


class Fonts:
    """全套字号。tkinter 的 tkfont.Font 必须在 Tk root 创建后再 new。"""

    def __init__(self, root):
        family = pick_font_family(root)
        self.family = family
        self.title   = tkfont.Font(root=root, family=family, size=16, weight="bold")
        self.heading = tkfont.Font(root=root, family=family, size=13, weight="bold")
        self.body    = tkfont.Font(root=root, family=family, size=12)
        self.small   = tkfont.Font(root=root, family=family, size=11)
        self.tiny    = tkfont.Font(root=root, family=family, size=10)
        self.mono    = tkfont.Font(root=root, family="DejaVu Sans Mono", size=11)
        self.kbd     = tkfont.Font(root=root, family=family, size=11, weight="bold")
