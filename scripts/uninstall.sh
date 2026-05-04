#!/usr/bin/env bash
# 卸载 voice-input systemd --user 服务。保留历史数据库和项目代码。

set -euo pipefail

UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
BIN_DIR="$HOME/.local/bin"
UNIT_NAME="voice-input.service"
UNIT_DST="$UNIT_DIR/$UNIT_NAME"
CLI_LINK="$BIN_DIR/voice-input"

systemctl --user disable --now "$UNIT_NAME" 2>/dev/null || true
rm -f "$UNIT_DST"
rm -f "$CLI_LINK"
systemctl --user daemon-reload

echo "✅ 已卸载 voice-input 服务和 CLI 软链。"
echo "   历史数据库保留在 ~/.local/share/voice-input/history.db，不会自动删除。"
