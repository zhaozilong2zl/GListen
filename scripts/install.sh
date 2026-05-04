#!/usr/bin/env bash
# 安装 voice-input 为 systemd --user 服务，开机/登录自动拉起。
# 幂等：重复执行只更新 unit 文件和 symlink。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
BIN_DIR="$HOME/.local/bin"
UNIT_NAME="voice-input.service"
UNIT_SRC="$PROJECT_DIR/scripts/voice-input.service.in"
UNIT_DST="$UNIT_DIR/$UNIT_NAME"
CLI_SRC="$PROJECT_DIR/cli.py"
CLI_LINK="$BIN_DIR/voice-input"

echo "==> 项目目录: $PROJECT_DIR"

# 前置检查
command -v systemctl >/dev/null || { echo "❌ 需要 systemd"; exit 1; }
[[ -x "$PROJECT_DIR/venv/bin/python" ]] || { echo "❌ venv 不存在: $PROJECT_DIR/venv"; exit 1; }
[[ -f "$PROJECT_DIR/voice_daemon.py" ]] || { echo "❌ 缺 voice_daemon.py"; exit 1; }

mkdir -p "$UNIT_DIR" "$BIN_DIR"

# 1) 生成 unit 文件（替换 PROJECT_DIR 占位符）
echo "==> 写入 unit 文件: $UNIT_DST"
sed "s|%PROJECT_DIR%|$PROJECT_DIR|g" "$UNIT_SRC" > "$UNIT_DST"

# 2) CLI symlink 到 ~/.local/bin/voice-input
chmod +x "$CLI_SRC"
if [[ -L "$CLI_LINK" || -f "$CLI_LINK" ]]; then
  rm -f "$CLI_LINK"
fi
ln -s "$CLI_SRC" "$CLI_LINK"
echo "==> CLI 软链: $CLI_LINK -> $CLI_SRC"

# 3) systemd 刷新
systemctl --user daemon-reload

# 4) 从当前登录会话导入 DISPLAY/XAUTHORITY 到 systemd --user 环境
#    不导入的话 ExecStart 里的 daemon 连不上 X server，pynput/xdotool/tk 全挂
if [[ -n "${DISPLAY:-}" ]]; then
  systemctl --user import-environment DISPLAY XAUTHORITY
  echo "==> 已导入 DISPLAY=$DISPLAY 到 systemd user env"
else
  echo "⚠️  当前 shell 没有 DISPLAY 环境变量，跳过 import。"
  echo "   登录桌面后再跑一次：systemctl --user import-environment DISPLAY XAUTHORITY"
fi

# 5) 启用 + 立刻启动
systemctl --user enable --now "$UNIT_NAME"

echo
echo "✅ 安装完成。"
echo
echo "常用命令："
echo "  状态:        systemctl --user status voice-input"
echo "  日志:        journalctl --user -u voice-input -f"
echo "  重启:        systemctl --user restart voice-input"
echo "  停止:        systemctl --user stop voice-input"
echo "  禁用自启:    systemctl --user disable voice-input"
echo "  查看历史:    voice-input history"
echo "  今日统计:    voice-input stats"
echo
echo "提示：按住 F9 说话，松开 F9 自动输入到当前焦点窗口。"
