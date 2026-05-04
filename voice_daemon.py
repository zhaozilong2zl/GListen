#!/usr/bin/env python3
"""
Step 2b: 按住 F9 录音、松开识别。
按 Ctrl+C 退出 daemon。

架构：
  pynput 线程 → F9 press/release 事件通过 asyncio.Event 传给主协程
  主协程 loop：等 F9 按下 → 开 session → 等 F9 松开 → 收尾 → 回到等待
"""
import asyncio
import json
import os
import re
import signal
import struct
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import history
import config as vi_config
import keys as vi_keys

# 豆包在国内，走本地翻墙代理会 TLS RST。直接清代理。
for _v in ("https_proxy", "http_proxy", "HTTPS_PROXY", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
    os.environ.pop(_v, None)

try:
    import websockets
    import websockets.exceptions
except ImportError:
    sys.exit("缺 websockets：在项目 venv 里运行 pip install 'websockets<16'")

try:
    from pynput import keyboard
except ImportError:
    sys.exit("缺 pynput：在项目 venv 里运行 pip install pynput")

CRED_FILE = Path.home() / ".config" / "doubao" / "credentials"
WS_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
CHANNELS = 1
CHUNK_MS = 100
CHUNK_BYTES = int(SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * CHUNK_MS / 1000)
FINAL_WAIT_SEC = 1.0  # 松开热键后等 Final 事件 / WS close 的超时（拿最准结果）

# 行为配置：优先从 config.json 读；env var 作为 fallback，保留向后兼容
_cfg = vi_config.load()
_beh = _cfg.get("behavior", {})
INPUT_MODE = os.environ.get("VOICE_INPUT_MODE") or _beh.get("input_mode", "paste")  # paste | type
PASTE_KEY = os.environ.get("VOICE_PASTE_KEY") or _beh.get("paste_key", "ctrl+shift+v")
DEBUG = (os.environ.get("VOICE_DEBUG") == "1") or bool(_beh.get("debug", False))
_overlay_env = os.environ.get("VOICE_OVERLAY")
OVERLAY_ENABLED = (_overlay_env != "0") if _overlay_env is not None else bool(_beh.get("overlay_enabled", True))
AUTO_PUNCTUATION = bool(_beh.get("auto_punctuation", True))
# 悬浮框跑在独立子进程里，用系统 /usr/bin/python3 —— 原因：anaconda 自带的
# libtk8.6.so 没链 libXft/libfontconfig，无法渲染 Noto CJK TrueType 字体，
# 所有中文字体都会 fallback 到 X core bitmap fixed。系统 libtk 链了 Xft 就正常。
OVERLAY_PYTHON = os.environ.get("VOICE_OVERLAY_PYTHON", "/usr/bin/python3")
OVERLAY_SCRIPT = str(Path(__file__).resolve().parent / "overlay_gui.py")


# ---------- 凭证 ----------
def load_credentials():
    if not CRED_FILE.exists():
        sys.exit(f"凭证文件不存在: {CRED_FILE}")
    creds = {}
    for line in CRED_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, _, v = line.partition("=")
        creds[k.strip()] = v.strip().strip("'\"")
    for k in ("APP_ID", "ACCESS_TOKEN", "RESOURCE_ID"):
        if k not in creds or not creds[k]:
            sys.exit(f"凭证缺字段: {k}")
    return creds


# ---------- 协议 ----------
def pack_first(payload_bytes):
    return struct.pack(">BBBB", 0x11, 0x10, 0x10, 0x00) + struct.pack(">I", len(payload_bytes)) + payload_bytes


def pack_audio(audio_bytes, final=False):
    msg_type_flags = (0b0010 << 4) | (0b0010 if final else 0b0000)
    return struct.pack(">BBBB", 0x11, msg_type_flags, 0x00, 0x00) + struct.pack(">I", len(audio_bytes)) + audio_bytes


def parse_response(data):
    """返回 (tag, payload, is_last)。is_last 从 flags 低 2 位判断（0b0010/0b0011=最后一包）。"""
    if len(data) < 4:
        return "short", None, False
    msg_type = (data[1] >> 4) & 0x0F
    flags = data[1] & 0x0F
    is_last = (flags & 0b0010) != 0
    idx = data.find(b"{", 4)
    if idx < 0:
        if msg_type == 0b1111:
            return "err", data[4:].decode("utf-8", errors="ignore"), is_last
        return f"msg_type=0x{msg_type:x}", data.hex()[:120], is_last
    payload = data[idx:]
    if msg_type == 0b1001:
        try:
            return "asr", json.loads(payload.decode("utf-8")), is_last
        except Exception as e:
            return "parse_err", f"{e}", is_last
    if msg_type == 0b1111:
        return "err", payload.decode("utf-8", errors="ignore"), is_last
    return f"msg_type=0x{msg_type:x}", data.hex()[:120], is_last


def extract_text(resp_json):
    r = resp_json.get("result")
    if isinstance(r, dict):
        return r.get("text", "")
    if isinstance(r, list):
        return "".join((x.get("text", "") if isinstance(x, dict) else str(x)) for x in r)
    if isinstance(r, str):
        return r
    return ""


# ---------- 后处理 ----------
def _compile_postprocess_rules(rules):
    """把 config 的规则编译成 (regex, sub_func) 列表。用 lambda 替换避免
    用户输入的 replacement 里的 \\1 \\2 被 re 误当成反向引用。
    """
    out = []
    for r in rules or []:
        if not r.get("enabled", True):
            continue
        pat = (r.get("pattern") or "").strip()
        if not pat:
            continue
        rep = r.get("replacement") or ""
        boundary = r.get("boundary", "word")
        try:
            if boundary == "word":
                regex = re.compile(
                    rf'([A-Za-z0-9_]+)\s*{re.escape(pat)}\s*([A-Za-z0-9_]+)'
                )
                sub = (lambda r_=rep: (lambda m: m.group(1) + r_ + m.group(2)))()
            else:  # always
                regex = re.compile(re.escape(pat))
                sub = (lambda r_=rep: (lambda m: r_))()
            out.append((regex, sub))
        except re.error:
            continue
    return out


_COMPILED_RULES = _compile_postprocess_rules(
    _cfg.get("postprocess", {}).get("rules")
)


# ---------- TranscriptAggregator ----------
# 严格 port 自 missuo/koe 的 koe-asr/src/transcript.rs。
# 豆包流式 ASR 的 result.text 在 VAD 分句后会重置（当前分句内累积，不跨分句），
# 所以客户端必须累积。koe 做的也是这个。
def longest_overlap(tail: str, head: str) -> int:
    """返回最长 k 使得 tail[-k:] == head[:k]。处理分段边界重叠字符。"""
    max_k = min(len(tail), len(head))
    for k in range(max_k, 0, -1):
        if tail[-k:] == head[:k]:
            return k
    return 0


class TranscriptAggregator:
    """累积 Interim / Definite / Final 三种事件为完整 transcript。"""

    def __init__(self):
        self.interim_text = ""
        self.definite_text = ""
        self.final_text = ""
        self.has_final = False
        self.has_definite = False

    def update_interim(self, text: str):
        if text:
            self.interim_text = text

    def update_definite(self, text: str):
        if text:
            self.has_definite = True
            self.definite_text = text
            self.interim_text = text  # definite 是"确认了的文本"，interim 同步更新让 live_preview 立刻可见

    def update_final(self, text: str):
        """按 koe 的规则合并 final。空→设，扩展→替换，回播→忽略，新段→按 overlap 拼接。"""
        self.has_final = True
        if not text:
            return
        if not self.final_text:
            self.final_text = text
        elif text.startswith(self.final_text):
            self.final_text = text  # 同分句的刷新版本
        elif self.final_text.startswith(text):
            return  # 服务端回播旧内容，忽略
        else:
            overlap = longest_overlap(self.final_text, text)
            self.final_text += text[overlap:]  # 新分段，去重叠拼接
        self.interim_text = ""  # 当前分句已 final，清空 interim

    def live_preview(self) -> str:
        """进行中显示：final + 当前 interim 的合并预览。"""
        if not self.final_text:
            return self.interim_text
        if not self.interim_text:
            return self.final_text
        if self.interim_text.startswith(self.final_text):
            return self.interim_text
        if self.final_text.startswith(self.interim_text):
            return self.final_text
        overlap = longest_overlap(self.final_text, self.interim_text)
        return self.final_text + self.interim_text[overlap:]

    def best_text(self) -> str:
        """最优可用文本。优先级: final > definite > interim。"""
        if self.has_final and self.final_text:
            return self.final_text
        if self.has_definite and self.definite_text:
            return self.definite_text
        return self.interim_text


# ---------- 悬浮框 ----------
class OverlayWindow:
    """
    启动一个 overlay_gui.py 子进程（用系统 /usr/bin/python3 跑，保证 Xft 能渲染中文），
    通过 stdin 发 JSON 命令控制显示。主 daemon 的 anaconda venv 完全不用碰 tkinter。
    """

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self._init_err = None

    def start(self):
        if not Path(OVERLAY_SCRIPT).exists():
            self._init_err = FileNotFoundError(OVERLAY_SCRIPT)
            return False
        if not Path(OVERLAY_PYTHON).exists():
            self._init_err = FileNotFoundError(OVERLAY_PYTHON)
            return False
        try:
            self._proc = subprocess.Popen(
                [OVERLAY_PYTHON, OVERLAY_SCRIPT],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                # binary 模式——配合 O_NONBLOCK 使 write 永不阻塞
            )
        except Exception as e:
            self._init_err = e
            return False
        # stdin 设为非阻塞：write 时如果 pipe buffer 满了直接跳过，不卡 asyncio loop
        import fcntl
        flags = fcntl.fcntl(self._proc.stdin.fileno(), fcntl.F_GETFL)
        fcntl.fcntl(self._proc.stdin.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)
        # 给子进程一点时间初始化 tk
        time.sleep(0.15)
        if self._proc.poll() is not None:
            err_out = ""
            try:
                err_out = self._proc.stderr.read() or b""
            except Exception:
                pass
            if isinstance(err_out, bytes):
                err_out = err_out.decode("utf-8", errors="replace")
            self._init_err = RuntimeError(f"overlay_gui exited rc={self._proc.returncode}: {err_out.strip()[:200]}")
            self._proc = None
            return False
        return True

    def _send(self, obj):
        """非阻塞写：pipe buffer 满了就丢这一帧，不卡调用方。"""
        p = self._proc
        if p is None or p.poll() is not None:
            return
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            os.write(p.stdin.fileno(), data)
        except (BlockingIOError, BrokenPipeError, OSError):
            pass  # buffer 满或 pipe 断了，跳过

    def show(self):
        self._send({"cmd": "show"})

    def update_text(self, text):
        self._send({"cmd": "text", "text": text or ""})

    def hide(self):
        self._send({"cmd": "hide"})

    def stop(self):
        if self._proc is None:
            return
        self._send({"cmd": "quit"})
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None


_WM_CLASS_RE = re.compile(r'WM_CLASS\(STRING\)\s*=\s*"[^"]*",\s*"([^"]*)"')
_NET_NAME_RE = re.compile(r'_NET_WM_NAME\([^)]+\)\s*=\s*"(.*)"\s*$', re.MULTILINE)
_WM_NAME_RE = re.compile(r'^WM_NAME\([^)]+\)\s*=\s*"(.*)"\s*$', re.MULTILINE)


def get_active_window_info():
    """抓当前焦点窗口的 WM_CLASS、标题和窗口 ID。
    F9 按下瞬间调用——记住目标窗口，松开后粘贴前先切回去。
    """
    try:
        r = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=0.5,
        )
        wid = r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        wid = ""
    if not wid:
        return None, None, None

    wm_class = None
    title = None
    try:
        r = subprocess.run(
            ["xprop", "-id", wid, "WM_CLASS", "_NET_WM_NAME", "WM_NAME"],
            capture_output=True, text=True, timeout=0.5,
        )
        out = r.stdout
        m = _WM_CLASS_RE.search(out)
        if m:
            wm_class = m.group(1) or None
        m = _NET_NAME_RE.search(out) or _WM_NAME_RE.search(out)
        if m:
            title = m.group(1) or None
    except Exception:
        pass
    return wm_class, title, wid


def focus_window(wid):
    """粘贴前切回按下热键时的目标窗口。解决录音过程中鼠标点了其他窗口的问题。"""
    if wid:
        try:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", str(wid)],
                check=False, timeout=1,
            )
        except Exception:
            pass


def input_text(text):
    """把文本输入到当前焦点窗口。paste 模式绕过输入法。"""
    if INPUT_MODE == "type":
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", "1", text],
            check=False, timeout=10,
        )
        return

    # paste 模式：保存剪贴板 → 复制新文字 → Ctrl+V → 恢复剪贴板
    old_clip = None
    try:
        old_clip = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, timeout=2,
        ).stdout
    except Exception:
        pass

    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text.encode("utf-8"), timeout=2, check=True,
        )
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", PASTE_KEY],
            check=False, timeout=3,
        )
    except Exception as e:
        print(f"⚠️  paste 失败，回退到 type: {e}")
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", "1", text],
            check=False, timeout=10,
        )

    # 给目标应用一点时间完成粘贴，再恢复剪贴板
    if old_clip is not None:
        time.sleep(0.15)
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=old_clip, timeout=2, check=False,
            )
        except Exception:
            pass


def copy_to_clipboard(text):
    """只复制，不粘贴。给 action 'clipboard' 用。"""
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text.encode("utf-8"), timeout=2, check=True,
        )
    except Exception as e:
        print(f"⚠️  复制到剪贴板失败: {e}")


def send_key_combo(combo):
    """xdotool key 发送一个键/组合键。combo 格式同 xdotool：enter / ctrl+s / shift+Return 等。"""
    try:
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", combo],
            check=False, timeout=3,
        )
    except Exception as e:
        print(f"⚠️  发送按键 {combo!r} 失败: {e}")


def execute_actions(text, actions):
    """按顺序执行 action chain。支持 paste / clipboard / press:<combo>。"""
    for action in actions or []:
        if action == "paste":
            try:
                input_text(text)
            except Exception as e:
                print(f"⚠️  paste 失败: {e}")
        elif action == "clipboard":
            copy_to_clipboard(text)
        elif action.startswith("press:"):
            combo = action[len("press:"):].strip()
            if combo:
                # 给前一步（paste）一点时间落地再按下一个键
                time.sleep(0.08)
                send_key_combo(combo)
        else:
            print(f"⚠️  未知 action: {action!r}")


def post_process(text):
    # 用户可编辑的规则（config.postprocess.rules）
    for regex, sub in _COMPILED_RULES:
        prev = None
        while prev != text:
            prev = text
            text = regex.sub(sub, text)
    # 内置规则保留（不适合表达为 pattern/replacement）：
    # 1) 连续单字母合并（"m a i n" → "main"）
    text = re.sub(r'(?:\b[a-zA-Z]\b\s*){2,}',
                  lambda m: ''.join(re.findall(r'[a-zA-Z]', m.group())),
                  text)
    # 2) 路径/扩展名位置的短大写自动转小写（SRC/ → src/, .PY → .py）
    text = re.sub(r'\b([A-Z]{2,5})/', lambda m: m.group(1).lower() + '/', text)
    text = re.sub(r'\.([A-Z]{1,5})\b', lambda m: '.' + m.group(1).lower(), text)
    return text


# ---------- 单次 session ----------
async def one_session(creds, release_event, overlay=None, meta=None):
    """按住 F9 期间持续录音 + 识别，松开 F9 结束。meta 携带 press_ts/wm_class/title 等信息。"""
    if overlay is not None:
        overlay.show()
    meta = meta or {}
    headers = {
        "X-Api-App-Key": creds["APP_ID"],
        "X-Api-Access-Key": creds["ACCESS_TOKEN"],
        "X-Api-Resource-Id": creds["RESOURCE_ID"],
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }
    first_req = {
        "user": {"uid": "voice_daemon"},
        "audio": {"format": "pcm", "rate": SAMPLE_RATE, "bits": SAMPLE_WIDTH * 8,
                  "channel": CHANNELS, "codec": "raw"},
        "request": {
            "model_name": "bigmodel",
            # 不设 language：留空时模型自动支持中英文混杂+方言
            "enable_itn": True,
            "enable_punc": AUTO_PUNCTUATION,  # 配置化。关掉避免"停顿自动变句号"
            "enable_ddc": False,        # 关顺滑：保留重复词、口误、语气词
            "enable_nonstream": True,   # 二遍识别，提升英文和整体准确率
            "result_type": "full",
            "show_utterances": True,    # 需要 utterances.definite 判断分句定稿事件
            # 不传 vad 字段：让 enable_nonstream 内部管 VAD（koe 也是这样）。
            # 客户端用 TranscriptAggregator 跨分句累积，不再依赖"避免分句"的策略。
        },
    }

    arecord = await asyncio.create_subprocess_exec(
        "arecord", "-f", "S16_LE", "-r", str(SAMPLE_RATE),
        "-c", str(CHANNELS), "-t", "raw", "-q",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    aggregator = TranscriptAggregator()

    try:
        async with websockets.connect(
            WS_URL, additional_headers=headers,
            open_timeout=20, ping_interval=None,
        ) as ws:
            await ws.send(pack_first(json.dumps(first_req).encode("utf-8")))
            print("\r🎙️  录音中...                                             ", end="", flush=True)

            async def sender():
                try:
                    while not release_event.is_set():
                        chunk = await arecord.stdout.read(CHUNK_BYTES)
                        if not chunk:
                            break
                        await ws.send(pack_audio(chunk, final=False))
                except Exception:
                    pass
                finally:
                    try:
                        await ws.send(pack_audio(b"", final=True))
                    except Exception:
                        pass

            async def receiver():
                """按 koe 的事件分发：is_last→Final，utterances.definite→Definite，否则 Interim。"""
                last_displayed = ""
                try:
                    while True:
                        msg = await ws.recv()
                        if not isinstance(msg, (bytes, bytearray)):
                            continue
                        tag, data, is_last = parse_response(bytes(msg))
                        if DEBUG and tag == "asr":
                            print(f"\n[DEBUG] is_last={is_last} data={json.dumps(data, ensure_ascii=False)[:300]}")
                        if tag == "asr":
                            text = post_process(extract_text(data))
                            utts = (data.get("result") or {}).get("utterances") or []
                            has_definite = any(
                                isinstance(u, dict) and u.get("definite") for u in utts
                            )
                            if is_last:
                                aggregator.update_final(text)
                            elif has_definite:
                                aggregator.update_definite(text)
                            else:
                                aggregator.update_interim(text)
                            display = aggregator.live_preview()
                            if display and display != last_displayed:
                                last_displayed = display
                                padding = " " * max(0, 60 - len(display))
                                print(f"\r🎙️  {display}{padding}", end="", flush=True)
                                if overlay is not None:
                                    overlay.update_text(display)
                        elif tag == "err":
                            print(f"\n[服务器错误] {data}")
                            return
                except websockets.exceptions.ConnectionClosedOK:
                    pass
                except websockets.exceptions.ConnectionClosedError as e:
                    print(f"\n[连接异常] {e}")

            sender_task = asyncio.create_task(sender())
            receiver_task = asyncio.create_task(receiver())

            # 等用户松开 F9
            await release_event.wait()
            release_ts = time.time()
            if overlay is not None:
                overlay.hide()
            if arecord.returncode is None:
                arecord.terminate()
            await sender_task
            # 等 Final 事件到达或 WS close（给二遍识别一点时间）
            try:
                await asyncio.wait_for(receiver_task, timeout=FINAL_WAIT_SEC)
            except asyncio.TimeoutError:
                receiver_task.cancel()

            # 取最终累积文本。aggregator 存的已经是 post_processed 版本
            # （receiver 里每次 update 前已经 post_process 过）。
            # 注：skip_postprocess 目前是 no-op，未来把 aggregator 改成存 raw 时才真正生效。
            final = aggregator.best_text()
            if final:
                hk = meta.get("hotkey") or {}
                print(f"\r✅ {final}" + " " * 10)

                # 粘贴前切回按下热键时的目标窗口（录音中用户可能点了其他窗口）
                focus_window(meta.get("target_wid"))
                # 执行 action chain（paste / clipboard / press:xxx）
                actions = hk.get("actions") or ["paste"]
                execute_actions(final, actions)

                # 写历史
                press_ts = meta.get("press_ts")
                duration_ms = int((release_ts - press_ts) * 1000) if press_ts else None
                try:
                    history.record(
                        text=final,
                        duration_ms=duration_ms,
                        wm_class=meta.get("wm_class"),
                        window_title=meta.get("window_title"),
                    )
                except Exception as e:
                    print(f"⚠️  历史写入失败: {e}")
            else:
                print("\r(无识别结果)                                                   ")
    finally:
        if overlay is not None:
            overlay.hide()
        if arecord.returncode is None:
            arecord.terminate()
            try:
                await asyncio.wait_for(arecord.wait(), timeout=1)
            except asyncio.TimeoutError:
                arecord.kill()


# ---------- 主 daemon ----------
async def main():
    creds = load_credentials()
    loop = asyncio.get_running_loop()

    overlay = None
    if OVERLAY_ENABLED:
        overlay = OverlayWindow()
        if not overlay.start():
            err = overlay._init_err
            print(f"⚠️  浮窗初始化失败，降级到纯终端模式: {err}")
            overlay = None

    press_event = asyncio.Event()
    release_event = asyncio.Event()
    quit_event = asyncio.Event()
    state = {
        "recording": False, "press_ts": None, "release_ts": None,
        "active_hotkey": None,  # 当前按住的 hotkey entry dict（主键或某个辅助键）
    }

    # 构建 pynput Key/KeyCode → hotkey entry 的映射表
    # 有无效键名（parse_key 返回 None）时，打印警告但不 crash，跳过那条
    hotkey_map = {}
    for entry in vi_config.all_hotkeys(_cfg):
        pk = vi_keys.parse_key(entry.get("key"))
        if pk is None:
            print(f"⚠️  热键 {entry.get('key')!r} 无法解析，已跳过（label={entry.get('label')!r}）")
            continue
        hotkey_map[pk] = entry

    if not hotkey_map:
        sys.exit("❌ 没有有效的热键配置，检查 config.json。")

    # XGrabKey 独占热键：让热键事件只发给我们，不到达目标应用。
    # 不 grab 的话按 Insert/PageUp 等键会同时触发原有功能。
    _xgrab_display = None
    try:
        from Xlib import X, display as xdisplay, XK
        _xgrab_display = xdisplay.Display()
        _xroot = _xgrab_display.screen().root
        for entry in vi_config.all_hotkeys(_cfg):
            key_name = entry.get("key", "")
            # config 字符串 → X11 keysym 名（如 "f9"→"F9", "insert"→"Insert", "page_up"→"Prior"）
            xksym_map = {
                "esc": "Escape", "enter": "Return", "backspace": "BackSpace",
                "tab": "Tab", "space": "space", "delete": "Delete",
                "insert": "Insert", "home": "Home", "end": "End",
                "page_up": "Prior", "page_down": "Next",
                "up": "Up", "down": "Down", "left": "Left", "right": "Right",
                "caps_lock": "Caps_Lock", "scroll_lock": "Scroll_Lock",
                "num_lock": "Num_Lock", "print_screen": "Print",
                "pause": "Pause", "menu": "Menu",
                "cmd": "Super_L", "shift": "Shift_L", "ctrl": "Control_L", "alt": "Alt_L",
            }
            if key_name.startswith("f") and key_name[1:].isdigit():
                xk_name = key_name.upper()  # f9 → F9
            elif key_name in xksym_map:
                xk_name = xksym_map[key_name]
            elif len(key_name) == 1:
                xk_name = key_name
            else:
                continue
            keysym = XK.string_to_keysym(xk_name)
            if keysym == 0:
                continue
            keycode = _xgrab_display.keysym_to_keycode(keysym)
            if keycode:
                _xroot.grab_key(keycode, X.AnyModifier, True,
                                X.GrabModeAsync, X.GrabModeAsync)
        _xgrab_display.sync()
        print("  热键已 grab（原有功能已屏蔽）")
    except Exception as e:
        print(f"  ⚠️  XGrabKey 失败，热键可能触发原有功能: {e}")

    def on_press(key):
        if state["recording"]:
            return
        entry = hotkey_map.get(key)
        if entry is None:
            return
        state["recording"] = True
        state["press_ts"] = time.time()
        state["release_ts"] = None
        state["active_hotkey"] = entry
        loop.call_soon_threadsafe(press_event.set)

    def on_release(key):
        if not state["recording"]:
            return
        entry = state.get("active_hotkey")
        # 只响应"释放的键"等于"按下时那个键"；避免按 F9 时恰好松开 F10 也触发结束
        if entry and key == vi_keys.parse_key(entry.get("key")):
            state["recording"] = False
            state["release_ts"] = time.time()
            loop.call_soon_threadsafe(release_event.set)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Ctrl+C 退出
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, quit_event.set)

    print("=" * 60)
    print("  GListen — glisten daemon 启动")
    print(f"  输入模式: {INPUT_MODE}  | 粘贴快捷键: {PASTE_KEY}")
    print(f"  悬浮框: {'开' if overlay else '关'}")
    print("  热键:")
    for entry in vi_config.all_hotkeys(_cfg):
        pk = vi_keys.parse_key(entry.get("key"))
        if pk is None:
            continue
        disp = vi_keys.display_name(entry.get("key", ""))
        label = entry.get("label") or "Dictate"
        actions = " → ".join(entry.get("actions") or ["paste"])
        print(f"    [{disp:>6}]  {label}  ({actions})")
    print("  🎙️  按住上述任一热键说话，松开执行对应动作")
    print("  ⏹️  Ctrl+C 退出")
    print("=" * 60)
    print()

    try:
        while not quit_event.is_set():
            # 等 F9 按下 或 退出信号
            press_task = asyncio.create_task(press_event.wait())
            quit_task = asyncio.create_task(quit_event.wait())
            done, pending = await asyncio.wait(
                {press_task, quit_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            if quit_event.is_set():
                break
            press_event.clear()

            # 在 main 协程里抓 WM_CLASS（而非 pynput 回调），避免 xdotool 阻塞 pynput 线程
            wm_class, window_title, target_wid = get_active_window_info()
            meta = {
                "press_ts": state["press_ts"],
                "wm_class": wm_class,
                "window_title": window_title,
                "target_wid": target_wid,
                "hotkey": state["active_hotkey"],
            }

            try:
                await one_session(creds, release_event, overlay=overlay, meta=meta)
            except asyncio.TimeoutError:
                print("\n❌ 豆包 WebSocket 握手超时。检查：")
                print("   1) 是否开着翻墙代理（clash 等，豆包在国内不要走墙外）")
                print("   2) 网络是否正常")
                if overlay is not None:
                    overlay.hide()
            except Exception as e:
                print(f"\n❌ session 异常: {type(e).__name__}: {e}")
                if overlay is not None:
                    overlay.hide()
            release_event.clear()
    finally:
        listener.stop()
        if overlay is not None:
            overlay.stop()
        # 释放 XGrabKey
        if _xgrab_display is not None:
            try:
                _xgrab_display.screen().root.ungrab_key(0, X.AnyModifier)
                _xgrab_display.sync()
                _xgrab_display.close()
            except Exception:
                pass

    print("\n再见")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
