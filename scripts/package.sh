#!/usr/bin/env bash
# 把项目打成可携带的 tar.gz，用于换电脑 / 分发给朋友。
# 产物默认在 /tmp/glisten-<日期>.tar.gz，解压到新机后 bash setup.sh 即可。
#
# 排除项：venv（新机重建）、历史 DB、缓存、设计稿原文件、git 元数据。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="glisten"
DATE=$(date +%Y%m%d)
OUT="${1:-/tmp/${NAME}-${DATE}.tar.gz}"

# 临时 staging 目录，避免路径不同导致 tar 里目录名混乱
STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT

# 用 rsync 复制文件，套用排除规则
rsync -a --quiet \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='design/' \
    --exclude='.git/' \
    --exclude='.claude/' \
    --exclude='.codex' \
    --exclude='.codex/' \
    --exclude='.vscode/' \
    --exclude='.idea/' \
    --exclude='*.db' \
    --exclude='*.db-journal' \
    --exclude='*.log' \
    --exclude='*.wav' \
    --exclude='*.tar.gz' \
    --exclude='out/' \
    "$PROJECT_DIR/" "$STAGING/$NAME/"

tar czf "$OUT" -C "$STAGING" "$NAME"

SIZE=$(du -h "$OUT" | awk '{print $1}')
echo "✅ 打包完成"
echo "   $OUT  ($SIZE)"
echo
echo "在新机上解压并安装："
echo "   tar xzf $(basename "$OUT")"
echo "   cd $NAME"
echo "   bash setup.sh"
