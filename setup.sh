#!/usr/bin/env bash
# Listen / glisten 一键安装脚本
# 换电脑或首次部署：cd glisten && bash setup.sh
#
# 幂等：重复跑只做必要的事。不会主动 sudo apt install —— 如果系统依赖缺失，
# 脚本会停下来打印需要的 apt 命令让你自己跑。

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRED_FILE="$HOME/.config/doubao/credentials"
VENV="$PROJECT_DIR/venv"

banner() {
    echo
    echo "━━━ $1 ━━━"
}

err() { echo "❌ $*" >&2; }
ok()  { echo "✓ $*"; }

banner "1/5 环境检查"

# 操作系统：必须是 apt-based Linux（Ubuntu / Debian / Pop!_OS 等）
if ! command -v apt >/dev/null 2>&1; then
    err "需要 apt-based 系统（Ubuntu / Debian）。其他发行版请自己替换包名装依赖。"
    exit 1
fi
ok "apt 可用"

# X11 会话
if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
    err "当前是 Wayland 会话 —— pynput 全局热键在 Wayland 下不工作，Listen 暂不支持。"
    err "请用 X11 会话登录（登录界面的齿轮图标选 'Ubuntu on Xorg'）"
    exit 1
fi
if [[ -z "${DISPLAY:-}" ]]; then
    err "DISPLAY 为空，看起来不是在图形会话里跑。请在桌面终端里执行 setup.sh"
    exit 1
fi
ok "X11 会话 DISPLAY=$DISPLAY"

# systemctl --user
if ! command -v systemctl >/dev/null 2>&1; then
    err "需要 systemd"
    exit 1
fi
ok "systemd 可用"

banner "2/5 系统依赖"

# binary 依赖用 command -v 检测；字体和 python-tk / python-venv 用 dpkg
declare -A BIN_TO_PKG=(
    ["xdotool"]="xdotool"
    ["xclip"]="xclip"
    ["xprop"]="x11-utils"
    ["arecord"]="alsa-utils"
)
MISSING_PKGS=()
for bin in "${!BIN_TO_PKG[@]}"; do
    if ! command -v "$bin" >/dev/null 2>&1; then
        MISSING_PKGS+=("${BIN_TO_PKG[$bin]}")
    fi
done

# python3-tk 和 python3-venv 没有对应 binary
for pkg in python3-tk python3-venv fonts-noto-cjk; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    # 去重
    UNIQ_PKGS=$(printf '%s\n' "${MISSING_PKGS[@]}" | sort -u | tr '\n' ' ')
    err "以下系统包缺失："
    echo "   $UNIQ_PKGS"
    echo
    echo "   装好后重新跑 setup.sh："
    echo
    echo "       sudo apt update && sudo apt install -y $UNIQ_PKGS"
    echo
    exit 1
fi
ok "系统依赖齐全（xdotool / xclip / xprop / arecord / python3-tk / python3-venv / fonts-noto-cjk）"

# 系统 python3 必须是 3.8+ 且带 tk（GUI 要用）
if ! /usr/bin/python3 -c "import tkinter" >/dev/null 2>&1; then
    err "系统 python3 无法 import tkinter —— 装 python3-tk 后重试"
    exit 1
fi
ok "/usr/bin/python3 支持 tkinter"

banner "3/5 Python venv"

if [[ ! -x "$VENV/bin/python" ]]; then
    echo "建 venv: $VENV"
    python3 -m venv "$VENV"
    ok "venv 已创建"
else
    ok "venv 已存在，跳过"
fi

if "$VENV/bin/python" -c "import websockets; import pynput" 2>/dev/null; then
    ok "Python 依赖已装，跳过"
else
    echo "pip install websockets<16 + pynput"
    "$VENV/bin/pip" install --quiet --upgrade pip \
        -i https://pypi.tuna.tsinghua.edu.cn/simple
    "$VENV/bin/pip" install --quiet 'websockets<16' pynput \
        -i https://pypi.tuna.tsinghua.edu.cn/simple
    ok "Python 依赖已装"
fi

banner "4/5 豆包凭证"

if [[ -s "$CRED_FILE" ]]; then
    ok "凭证已存在: $CRED_FILE"
    echo "   如果需要改，直接编辑该文件（APP_ID / ACCESS_TOKEN / RESOURCE_ID 三个字段）"
else
    echo "豆包凭证还没配。从火山控制台拿："
    echo "  https://console.volcengine.com/speech/app"
    echo "  → 开通「豆包流式语音识别模型 2.0」"
    echo "  → 在应用详情页拿 APP_ID（纯数字）和 Access Token（长字符串）"
    echo
    read -rp "APP_ID (纯数字): " APP_ID
    read -rp "Access Token: " ACCESS_TOKEN
    read -rp "Resource ID [回车=默认 volc.seedasr.sauc.duration]: " RESOURCE_ID
    RESOURCE_ID="${RESOURCE_ID:-volc.seedasr.sauc.duration}"

    mkdir -p "$(dirname "$CRED_FILE")"
    (
        umask 077
        cat > "$CRED_FILE" <<EOF
APP_ID=$APP_ID
ACCESS_TOKEN=$ACCESS_TOKEN
RESOURCE_ID=$RESOURCE_ID
EOF
    )
    ok "凭证已写入 $CRED_FILE（权限 600）"
fi

banner "5/5 注册 systemd --user 服务"

bash "$PROJECT_DIR/scripts/install.sh"

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 安装完成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "  按住 F9 说话，松开输入到光标。"
echo
echo "  常用命令："
echo "    glisten config         打开设置窗（改热键 / 规则 / 查历史）"
echo "    glisten history        CLI 查最近 20 条"
echo "    glisten stats          统计 / DB 大小"
echo "    systemctl --user status glisten     服务状态"
echo "    journalctl --user -u glisten -f     实时日志"
echo
