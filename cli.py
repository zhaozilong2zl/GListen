#!/usr/bin/env python3
"""
voice-input CLI 入口。安装后 symlink 到 ~/.local/bin/voice-input。

子命令：
  voice-input daemon                    启动守护进程（systemd ExecStart 用这个）
  voice-input history [-n 20] [-s KW] [--today] [--days N]
                                        查看识别历史
  voice-input stats                     统计总条数/总时长/今日条数

注意：本文件用 `/usr/bin/env python3` 当 shebang，但 daemon 子命令会 exec 到
venv 的 python（daemon 需要 venv 里的 websockets/pynput），所以即使 CLI 被
系统 python3 调用，daemon 仍跑在正确的 venv 里。
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

VENV_PYTHON = PROJECT_DIR / "venv" / "bin" / "python"
DAEMON_SCRIPT = PROJECT_DIR / "voice_daemon.py"
SYSTEM_PYTHON = Path("/usr/bin/python3")
GUI_ENTRY = PROJECT_DIR / "listen_gui" / "main.py"


def cmd_daemon(args):
    if not VENV_PYTHON.exists():
        sys.exit(f"venv python 不存在: {VENV_PYTHON}")
    if not DAEMON_SCRIPT.exists():
        sys.exit(f"daemon 脚本不存在: {DAEMON_SCRIPT}")
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(DAEMON_SCRIPT)])


def cmd_config(args):
    """启动 GListen 设置窗口。必须用系统 python3（anaconda tk 渲染不了中文）。"""
    if not SYSTEM_PYTHON.exists():
        sys.exit(f"系统 python3 不存在: {SYSTEM_PYTHON}")
    if not GUI_ENTRY.exists():
        sys.exit(f"GUI 入口不存在: {GUI_ENTRY}")
    os.execv(str(SYSTEM_PYTHON), [str(SYSTEM_PYTHON), str(GUI_ENTRY)])


def _truncate(s, n):
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1] + "…"


def cmd_history(args):
    import history as hist
    rows = hist.query(
        limit=args.limit,
        search=args.search,
        today=args.today,
        since_days=args.days,
    )
    if not rows:
        print("(无记录)")
        return
    # 列宽参考：时间 19 + 时长 6 + wm_class 18 + text 余下
    for _id, ts, text, dur_ms, wm, _title in rows:
        when = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        dur = f"{dur_ms/1000:>4.1f}s" if dur_ms else "  -  "
        wm_str = _truncate(wm or "-", 18)
        print(f"{when}  {dur}  {wm_str:<18}  {text}")


def _fmt_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n/1024:.1f} KB"
    return f"{n/1024**2:.1f} MB"


def cmd_stats(args):
    import history as hist
    s = hist.stats()
    print(f"总计：{s['total']} 条，累计录音 {s['total_minutes']} 分钟")
    print(f"今日：{s['today']} 条")
    if s["first_ts"]:
        first = datetime.fromtimestamp(s["first_ts"]).strftime("%Y-%m-%d")
        print(f"最早一条：{first}")
    print(f"数据库：{hist._db_path()}  ({_fmt_size(s['db_bytes'])})")


def cmd_prune(args):
    import history as hist
    s = hist.stats()
    if not args.yes:
        print(f"即将删除 {args.days} 天之前的记录。")
        print(f"当前总计 {s['total']} 条，DB 大小 {_fmt_size(s['db_bytes'])}。")
        ans = input("确认？(y/N) ").strip().lower()
        if ans not in ("y", "yes"):
            print("取消。")
            return
    deleted = hist.prune(args.days)
    after = hist.stats()
    print(f"已删除 {deleted} 条。剩余 {after['total']} 条，DB 大小 {_fmt_size(after['db_bytes'])}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="voice-input",
        description="Linux 语音输入 daemon (豆包 ASR 2.0) + 历史查询",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_daemon = sub.add_parser("daemon", help="启动语音输入守护进程")
    p_daemon.set_defaults(func=cmd_daemon)

    p_config = sub.add_parser("config", help="打开 GListen 设置窗口（GUI）")
    p_config.set_defaults(func=cmd_config)

    p_hist = sub.add_parser("history", help="查看识别历史")
    p_hist.add_argument("-n", "--limit", type=int, default=20, help="最多显示几条，默认 20")
    p_hist.add_argument("-s", "--search", help="按文本关键词模糊搜索")
    g = p_hist.add_mutually_exclusive_group()
    g.add_argument("--today", action="store_true", help="只看今天")
    g.add_argument("--days", type=int, help="最近 N 天")
    p_hist.set_defaults(func=cmd_history)

    p_stats = sub.add_parser("stats", help="统计总条数/时长/DB 大小")
    p_stats.set_defaults(func=cmd_stats)

    p_prune = sub.add_parser("prune", help="清理 N 天之前的历史记录（破坏性，需确认）")
    p_prune.add_argument("--days", type=int, required=True, help="保留多少天之内的记录")
    p_prune.add_argument("-y", "--yes", action="store_true", help="跳过确认提示")
    p_prune.set_defaults(func=cmd_prune)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
