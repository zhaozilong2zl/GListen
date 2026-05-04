"""
Listen / voice-input 配置读写。

路径：$XDG_CONFIG_HOME/voice-input/config.json（默认 ~/.config/voice-input/config.json）

schema:
{
  "hotkeys": {
    "main": {
      "key": "f9",                      # 主热键（pynput Key 名 或 单字符）
      "label": "Dictate",
      "actions": ["paste"],             # 识别完成后按顺序执行的动作
      "skip_postprocess": false
    },
    "auxiliary": [
      {"key": "f10", "label": "…",
       "actions": ["paste", "press:enter"],
       "skip_postprocess": false},
      ...
    ]
  },
  "behavior": {
    "input_mode": "paste",              # paste | type
    "paste_key": "ctrl+shift+v",        # paste 模式下发送的快捷键
    "overlay_enabled": true,
    "debug": false
  }
}

支持的动作（action chain 里的字符串）：
  paste                       粘贴识别结果到光标
  clipboard                   复制到剪贴板（不粘贴）
  press:<combo>               执行完上面后，再按一个键或组合键
                              combo 格式对齐 xdotool key 参数：
                              press:enter / press:tab / press:shift+enter / press:ctrl+s
"""
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "voice-input" / "config.json"


DEFAULT_CONFIG: Dict[str, Any] = {
    "hotkeys": {
        "main": {
            "key": "f9",
            "label": "Dictate",
            "actions": ["paste"],
            "skip_postprocess": False,
        },
        "auxiliary": [],
    },
    "behavior": {
        "input_mode": "paste",
        "paste_key": "ctrl+shift+v",
        "overlay_enabled": True,
        "auto_punctuation": True,   # 豆包 enable_punc。关掉能避免"停顿变句号"
        "debug": False,
    },
    # 后处理规则。boundary:
    #   word  —— 两侧必须都是 [A-Za-z0-9_]+ 才替换（避免误伤「重点」「观点」）
    #   always —— 任何位置都替换（适合纯文本替换，比如「克劳德」→「Claude」）
    "postprocess": {
        "rules": [
            {"pattern": "点",     "replacement": ".", "boundary": "word", "enabled": True},
            {"pattern": "斜杠",   "replacement": "/", "boundary": "word", "enabled": True},
            {"pattern": "下划线", "replacement": "_", "boundary": "word", "enabled": True},
            {"pattern": "横线",   "replacement": "-", "boundary": "word", "enabled": True},
            {"pattern": "冒号",   "replacement": ":", "boundary": "word", "enabled": True},
        ],
    },
}


def _merge(defaults: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并 user 到 defaults 副本上。user 里多余的 key 保留；缺的字段用 defaults 补齐。"""
    out = deepcopy(defaults)
    for k, v in user.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> Dict[str, Any]:
    """读配置。文件不存在或解析失败时返回默认配置（不写盘）。"""
    p = config_path()
    if not p.exists():
        return deepcopy(DEFAULT_CONFIG)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(DEFAULT_CONFIG)
    if not isinstance(data, dict):
        return deepcopy(DEFAULT_CONFIG)
    return _merge(DEFAULT_CONFIG, data)


def save(config: Dict[str, Any]) -> None:
    """原子写：先写临时文件，再 rename。避免写到一半断电导致 config 损坏。"""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, p)


def all_hotkeys(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """返回 main + auxiliary 合并后的热键列表，第一个永远是 main。"""
    cfg = config if config is not None else load()
    hk = cfg.get("hotkeys", {})
    main = hk.get("main") or DEFAULT_CONFIG["hotkeys"]["main"]
    aux = hk.get("auxiliary") or []
    return [main] + list(aux)
