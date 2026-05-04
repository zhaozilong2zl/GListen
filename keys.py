"""
热键名转换辅助。

三个命名空间要互转：
  1. config.json 里的字符串（小写，规范化）：'f9', 'pause', 'caps_lock', '`'
  2. pynput 的 Key / KeyCode 对象（daemon 监听用）
  3. tkinter 事件的 event.keysym（GUI 捕获按键时 tk 给的名字：'F9', 'Pause', 'Caps_Lock'）

pynput import 是 lazy 的 —— GUI 跑在系统 python3 下（tkinter Xft 要求）可能没装 pynput。
"""
from typing import Any, Optional


# tkinter keysym → 我们用的规范字符串
# tkinter 的 X11 keysym 命名和 pynput 不完全一致，这张表做翻译
_TK_TO_NAME = {
    "Escape": "esc",
    "Return": "enter",
    "Caps_Lock": "caps_lock",
    "Scroll_Lock": "scroll_lock",
    "Num_Lock": "num_lock",
    "Print": "print_screen",
    "Pause": "pause",
    "BackSpace": "backspace",
    "Tab": "tab",
    "Delete": "delete",
    "Insert": "insert",
    "Home": "home",
    "End": "end",
    "Prior": "page_up",      # X11 里 PageUp 叫 Prior
    "Next": "page_down",     # X11 里 PageDown 叫 Next
    "Up": "up",
    "Down": "down",
    "Left": "left",
    "Right": "right",
    "Menu": "menu",
    "Super_L": "cmd",
    "Super_R": "cmd",
    "space": "space",
}


def tk_keysym_to_name(keysym: str) -> Optional[str]:
    """把 tkinter event.keysym 转成我们的规范字符串（用于保存到 config）。
    修饰键（Shift/Ctrl/Alt）返回 None —— 主热键不允许是纯修饰键。
    """
    if keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R",
                  "Alt_L", "Alt_R", "ISO_Level3_Shift"):
        return None
    if keysym in _TK_TO_NAME:
        return _TK_TO_NAME[keysym]
    # F1 ~ F20
    if len(keysym) >= 2 and keysym[0] == "F" and keysym[1:].isdigit():
        n = int(keysym[1:])
        if 1 <= n <= 20:
            return f"f{n}"
    # 单字符（字母数字符号）
    if len(keysym) == 1:
        return keysym.lower()
    # 其他不认识的按键原样小写返回，让上层决定怎么处理
    return keysym.lower()


def parse_key(name: str) -> Any:
    """把 config 里的字符串转成 pynput Key / KeyCode 对象。
    lazy import pynput —— GUI 侧可以不装 pynput，只要不调这个函数就行。
    """
    from pynput import keyboard  # type: ignore
    name = (name or "").lower().strip()
    if not name:
        return None
    # pynput 的 Key enum
    if hasattr(keyboard.Key, name):
        return getattr(keyboard.Key, name)
    # 单字符
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    return None


def display_name(name: str) -> str:
    """人类可读名，用于 UI 上 Kbd 键帽显示。"""
    name = (name or "").strip()
    if not name:
        return "—"
    special = {
        "esc": "Esc",
        "enter": "Enter",
        "space": "Space",
        "tab": "Tab",
        "delete": "Del",
        "backspace": "⌫",
        "caps_lock": "Caps",
        "scroll_lock": "ScrLk",
        "num_lock": "NumLk",
        "print_screen": "PrtSc",
        "pause": "Pause",
        "page_up": "PgUp",
        "page_down": "PgDn",
        "home": "Home",
        "end": "End",
        "insert": "Ins",
        "up": "↑", "down": "↓", "left": "←", "right": "→",
        "cmd": "Super",
        "menu": "Menu",
    }
    if name in special:
        return special[name]
    # f1 ~ f20
    if name.startswith("f") and name[1:].isdigit():
        return name.upper()
    # 单字符
    if len(name) == 1:
        return name.upper() if name.isalpha() else name
    return name
