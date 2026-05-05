# GListen —— Linux 系统实时语音输入工具。

**Linux 上的实时语音输入工具。** 按住热键说话，松开后文字自动粘贴到当前焦点窗口，同时保存历史语音识别结果。后端使用[豆包流式语音识别 2.0](https://www.volcengine.com/docs/6561/163043)（字节跳动，注册即送20h额度）。

[English Version](README_EN.md)

```
切到任意窗口 → 按住热键 → 说话 → 松开 → 文字粘贴到该窗口
                  ↑ 鼠标附近会弹出浮窗显示实时识别文本
```

<p align="center">
  <img src="docs/screenshots/hud-live.png" width="500" alt="实际使用效果展示">
</p>

<p align="center">
  <img src="docs/screenshots/GUI-shortcuts.png" width="500" alt="GListen GUI 设置中心 — 快捷键页">
</p>

<p align="center">
  <img src="docs/screenshots/GUI-behavior.png" width="500" alt="GListen GUI 设置中心 — 行为页">
</p>

<p align="center">
  <img src="docs/screenshots/GUI-post_processing.png" width="500" alt="GListen GUI 设置中心 — 后处理页">
</p>

<p align="center">
  <img src="docs/screenshots/GUI-history.png" width="500" alt="GListen GUI 设置中心 — 历史页">
</p>

<p align="center">
  <img src="docs/screenshots/GUI-about.png" width="500" alt="GListen GUI 设置中心 — 关于页">
</p>



## 功能

### 按住说话，松开输入

焦点切到任意窗口（终端、浏览器、编辑器、聊天框），按住热键（默认 F9）开始说话。说话过程中鼠标附近会弹出一个半透明黑色浮窗，实时显示当前识别到的文字——说到哪里显示到哪里，不需要等说完，这就是流式识别。松开热键，最终识别结果自动粘贴到焦点窗口（或者复制到粘贴板，这个功能可自己添加热键diy，见下面的介绍）。

### 多热键 + 动作链

除了默认的"录完粘贴"，你可以给其他按键绑定不同的动作组合。比如：

- **F9**（默认）：录完 → 粘贴到焦点窗口
- **F10**：录完 → 粘贴 → 自动按 Enter 发送（适合聊天窗口，说完直接发出去）
- **F11**：录完 → 只复制到剪贴板，不粘贴（你自己选时机贴）

在 GUI 设置中心的"快捷键"页面里添加，可添加多个热键。

### 后处理规则

编程时经常需要口述符号——"settings 点 json" 会被 ASR 识别成文字 `settings 点 json`。后处理规则自动把两个英文词之间的"点"替换成 `.`，变成 `settings.json`。类似的内置规则还有"斜杠"→`/`、"下划线"→`_` 等。

你也可以在 GUI 里自定义规则，比如把"克劳德"替换成"Claude"、"派森"替换成"Python"。规则分两种模式：**只在英文词之间替换**（不会把"重点"误改成"重."）和**任何位置替换**（适合专有名词）。

### GUI 设置中心

运行 `glisten config` 打开设置窗口，5 个页面：

- **快捷键**：重新绑定主热键、添加/编辑/删除辅助热键
- **行为**：输入方式（剪贴板粘贴 / 逐字模拟）、粘贴快捷键、浮窗开关、自动标点开关
- **后处理**：管理替换规则，每条可单独开关
- **历史**：以时间轴形式查看所有识别记录，支持搜索和按日期筛选
- **关于**：服务运行状态、一键重启/停止、查看日志、凭证和数据库路径

改完任何设置后服务会自动重启（约 1-2 秒），新配置立刻生效。

### 识别历史

每次语音输入的结果都会自动保存到本地 SQLite 数据库，记录识别文本、录音时长、目标窗口等信息。可以通过命令行（`glisten history`）或 GUI 历史页面查看、搜索、删除。

### 系统服务

安装后自动注册为 systemd 用户服务，开机登录就在后台运行，不需要手动启动。进程意外退出也会自动重启。日志可以用 `journalctl --user -u glisten` 查看。

## 快速开始

### 环境要求

- **Ubuntu / Debian**（apt 系）+ **x11 桌面会话**
- 系统包：`xdotool` `xclip` `x11-utils` `alsa-utils` `python3-tk` `python3-venv` `fonts-noto-cjk`
- Python 3.8+（系统）+ Python 3.10+（venv，装 websockets / pynput）
- **豆包 ASR 2.0 凭证**——去[火山引擎控制台](https://console.volcengine.com/speech/app)开通"豆包流式语音识别模型 2.0"，拿到 APP_ID 和 Access Token

> **关于 X11 和 Wayland 适配**：GListen 使用的几个系统工具（pynput 全局热键监听、xdotool 文字注入、xclip 剪贴板）都是 X11 生态下的标准工具。Ubuntu 22.04 及之前默认是 X11，不需要做任何设置。Ubuntu 24.04+ 默认改为了 Wayland，由于 Wayland 的安全模型禁止应用监听其他窗口的键盘事件和注入文字，GListen将无法工作。如果你的系统是 24.04+，需要在开机登录界面（输密码的那个页面）右下角的齿轮图标里选择 "Ubuntu on Xorg"。

### 安装

```bash
git clone https://github.com/zhaozilong2zl/glisten.git
cd glisten
bash setup.sh
```

`setup.sh` 做如下 5 件事：

1. 检查 x11 + apt + systemd 环境
2. 检查系统依赖——**不会自动装**，缺的话打印 `sudo apt install ...` ，需要粘贴到命令行运行
3. 创建 Python venv，安装 `websockets<16` + `pynput`（清华镜像源）
4. 交互式输入豆包凭证（APP_ID / Access Token / Resource ID）→ 写到 `~/.config/doubao/credentials`，权限 600
5. 注册 systemd --user 服务并启动

装完以后，**按住热键（默认 F9）说话，松开即粘贴到当前焦点窗口**。

## 使用

### 日常

不需要手动操作——服务登录后自动运行。按住热键说话，松开即可。

### 命令行

```bash
glisten history              # 最近 20 条识别记录
glisten history -s 关键词    # 搜索
glisten history --today      # 只看今天
glisten stats                # 统计：条数 / 录音分钟 / DB 大小
glisten config               # 打开 GUI 设置窗口
```

### GUI 设置（`glisten config`）

| 页面 | 功能 |
|---|---|
| **快捷键** | 重新绑定主热键（按键捕获）；添加辅助热键 + 动作链（如 F10 = 粘贴 + 按 Enter） |
| **行为** | 输入方式（paste / type）、粘贴快捷键、悬浮框开关、自动标点开关 |
| **后处理** | 增删替换规则：`点 → .`（只在英文词之间替换，不会把「重点」变成「重.」）、`克劳德 → Claude`（任何位置） |
| **历史** | 时间轴视图 + 装饰波形、搜索、筛选（全部 / 今天 / 最近 7 天）、复制 / 删除 |
| **关于** | 服务状态、重启 / 停止 / 查看日志、凭证和 DB 路径、火山控制台链接 |

任何改动立即生效（写入配置 → 自动重启服务，中断约 1-2 秒）。

### 服务管理

```bash
systemctl --user status glisten       # 查看状态
systemctl --user restart glisten      # 重启
journalctl --user -u glisten -f       # 实时日志
```

## 项目背景

大多数语音输入软件只为 Windows 和 macOS 而设计——[Wispr Flow](https://wisprflow.com/)、[Superwhisper](https://superwhisper.com/)、[Typeless](https://www.typeless.com/)、[闪电说](https://shandianshuo.cn/)，这些产品在 Windows 和 macOS 上百花齐放，但截至 2026 年 5 月没有一个支持 Linux。主要原因可能是：macOS 和 Windows 各有一套统一的系统级输入 API，开发一套就能全平台通用；而 Linux 桌面环境碎片化严重（X11 / Wayland / GNOME / KDE / i3 …），且用户基数非常小，所以在相近的开发投入下，商业产品适配Linux系统的成本相比之下非常高。

Linux 上不是完全没选择，但都有各自的限制：

- [Claude Code](https://code.claude.com/) / [Codex](https://openai.com/) 等 AI 工具内置了语音输入（虽然 Claude Code 对中文支持非常有限），但**只能在自家 CLI 或 App 内使用**，没法输入到浏览器、编辑器、聊天窗口
- [Voxtype](https://github.com/peteonrails/voxtype)、[nerd-dictation](https://github.com/ideasman42/nerd-dictation) 等开源方案走本地模型（Whisper / VOSK），但本地小模型对中英混杂短句准确率不太理想（大模型准确率好一些，但需要较好的 GPU，且速度慢（这也是LLM本地部署面临的困境，本地可以部署，但是跟厂商提供的api效果始终有差距））；而且这些方案都是**录完再识别**，做不到边说边出字的实时体验
- Linux 桌面环境（GNOME / KDE）至今没有原生的语音输入功能

基于此，我花了一点时间（当然还有 token）做了这个小工具。它用豆包云端大模型做识别，对中英文混杂的准确率比本地 Whisper 小模型好不少，而且是实时流式的——说到哪里显示到哪里，松开热键就粘贴，不用等全说完才能看到输出结果。

在 vibe coding 时代，做出这样一个小工具不是什么难事。我只是把我的一些 token 的结晶分享出来，如果能恰好帮助有类似需求的同志（或者联网搜索到这个项目的agent）省一点从头造轮子的 token，那就太好了。

## 现有产品对比

| 工具 | 平台 | 识别后端 | 中文 | 实时流式 | 多热键 | GUI |
|---|---|---|---|---|---|---|
| **GListen** | **Linux (x11)** | 豆包 2.0（云端） | 是 | 是 | 是 | 是 |
| [Typeless](https://www.typeless.com/) | macOS/Win/iOS/Android | 云端 AI | 是 | 是 | 否 | 是 |
| [闪电说](https://shandianshuo.cn/) | macOS/Win | 本地端侧 + 可选 LLM API | 是 | 是 | 否 | 是 |
| [Wispr Flow](https://wisprflow.com/) | macOS/Win/iOS/Android | 云端自研 | 是 | 是 | 否 | 是 |
| [Superwhisper](https://superwhisper.com/) | macOS/Win/iOS | Whisper 本地+云端 | 是 | 否 | 否 | 是 |
| [Koe](https://github.com/missuo/koe) | 仅 macOS | 豆包 2.0（云端） | 是 | 是 | 否 | 否 |
| [Voxtype](https://github.com/peteonrails/voxtype) | Linux（Wayland 为主） | Whisper 本地 | 是 | 否 | 否 | 否 |
| [Speed of Sound](https://github.com/zugaldia/speedofsound) | Linux (Flatpak) | Whisper + 可选 LLM | 是 | 否 | 否 | 是 |
| [nerd-dictation](https://github.com/ideasman42/nerd-dictation) | Linux | VOSK 本地 | 弱 | 否 | 否 | 否 |
| [Talon Voice](https://talonvoice.com/) | macOS/Win/Linux | Conformer 本地 | 以英文为主 | 是 | 是 | 否 |
| macOS 听写 | macOS | Apple 本地 | 是 | 是 | 系统按键 | 系统 |
| Windows 语音输入 | Windows 11 | Azure 云端 | 是 | 是 | Win+H | 系统 |

GListen 需要联网 + 火山引擎账号（当然你可以 DIY 成本地模型，或者适配其他的 API）。

## 工作原理

整个过程分三个阶段：

**按住热键时**：开始录音（arecord 采集 16kHz PCM 音频），音频通过 WebSocket 实时发送给豆包 ASR 2.0。豆包每收到一段音频就返回当前识别结果（partial 帧），客户端的 Transcript Aggregator 负责把多次返回的片段拼成完整文本（因为豆包在语音停顿时会重置当前句，需要客户端自己跨句累积）。浮窗 HUD 在这个阶段实时显示拼接后的文字。

**松开热键时**：停止录音，发送结束帧。豆包做最后一轮识别（如果开了 `enable_nonstream` 二遍识别，会用更大的模型重新校正一次），返回最终结果。

**识别完成后**：对最终文本做后处理（应用"点"→"."等替换规则），然后按配置的动作链依次执行：复制到剪贴板 → 模拟粘贴快捷键 → 如果配了额外按键（比如 Enter）再按一下。

```
按住热键
  ├→ 录音，音频流式发送给豆包
  ├→ 豆包持续返回识别结果，浮窗实时显示
  │
松开热键
  ├→ 停止录音，等待最终识别结果
  ├→ 后处理（"点"→"."）
  └→ 粘贴到目标窗口
```

## 配置格式

`~/.config/glisten/config.json`：

```jsonc
{
  "hotkeys": {
    "main": { "key": "f9", "label": "Dictate", "actions": ["paste"] },
    "auxiliary": [
      { "key": "f10", "label": "录音并发送", "actions": ["paste", "press:Return"] }
    ]
  },
  "behavior": {
    "input_mode": "paste",          // paste（剪贴板粘贴）| type（逐字模拟）
    "paste_key": "ctrl+shift+v",    // 终端友好的默认值
    "overlay_enabled": true,
    "auto_punctuation": true,       // 豆包 enable_punc，关掉可避免停顿变句号
    "debug": false
  },
  "postprocess": {
    "rules": [
      { "pattern": "点", "replacement": ".", "boundary": "word", "enabled": true }
      // boundary: "word" = 只在英文词之间替换（"重点"不受影响）；"always" = 出现就替换
    ]
  }
}
```

## 换电脑

换了新电脑想在保留原来电脑的识别历史记录的情况下继续使用，请执行下面两步：

**1. 在老电脑上打包**

```bash
bash scripts/package.sh
```

会在 `/tmp/` 下生成一个压缩包（很小，不含 Python 环境和个人凭证），用 U 盘、网盘或 `scp` 等方式传到新电脑。

**2. 在新电脑上安装**

```bash
tar xzf glisten-*.tar.gz
cd glisten
bash setup.sh
```

`setup.sh` 会引导你装依赖、建环境、填豆包凭证，和第一次安装流程一样。凭证不在压缩包里（安全考虑，防止不慎泄漏在互联网的黑暗森林中被盗用），需要重新从[火山引擎控制台](https://console.volcengine.com/speech/app)拿 APP_ID 和 Access Token 填一遍。

## 卸载 / 重装

如果需要卸载或者重新安装，**一定要先停掉旧服务再装新的**，否则会出现两个进程同时抢热键的情况（两个浮窗、识别失败）。

```bash
# 卸载（停止服务 + 删除 unit 文件 + 删除 CLI 软链）
bash scripts/uninstall.sh

# 如果要重装，卸载后直接重新跑 setup.sh
bash setup.sh
```

卸载不会删除你的配置（`~/.config/glisten/`）、历史记录（`~/.local/share/glisten/`）和豆包凭证（`~/.config/doubao/`），重装后这些数据还在。

## 项目结构

| 文件 | 职责 |
|---|---|
| `voice_daemon.py` | 主守护进程：热键监听 + 豆包 WS + 动作链 + 历史写入 |
| `overlay_gui.py` | 浮窗 HUD 子进程（系统 python3，Xft 渲染中文） |
| `glisten_gui/` | GListen 设置中心（tkinter，5 页） |
| `config.py` | 配置读写（JSON schema + 默认值 + 原子写入） |
| `keys.py` | 键名转换：配置字符串 ↔ pynput Key ↔ tkinter keysym |
| `history.py` | SQLite 历史模块 |
| `cli.py` | CLI 入口，软链为 `~/.local/bin/glisten` |
| `setup.sh` | 换机一键安装脚本 |
| `scripts/` | systemd unit 模板、安装 / 卸载 / 打包脚本 |

## 致谢

- **[missuo/koe](https://github.com/missuo/koe)**（MIT）——TranscriptAggregator 的累积逻辑（interim / definite / final 三类事件、longest-overlap 去重叠拼接）参考了其 Rust 实现 `koe-asr/src/transcript.rs`
- **[zhouruhui/volcengine-asr-ha](https://github.com/zhouruhui/volcengine-asr-ha)**（MIT）——WebSocket 二进制帧协议（pack / parse）参考了其 Python 实现

## 联系方式
2507844603@qq.com

## License

MIT
