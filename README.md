# text-to-speech

供 **Codex 和 Claude Code** 使用的文字转语音 Skill。支持命名克隆音色、列出本机音色、将文字生成 MP3/WAV，以及语速调整、实验性情绪指令和指定停顿。

## 环境要求

- 安装脚本需要 Bash、curl、Git 和 Python 3，推荐 Python 3.12。语音脚本首次使用时会准备持久 Python 环境及对应依赖。
- Edge 预设音色需要联网；本机原声克隆使用 Apple Silicon Mac。
- 麦克风现场录制目前支持 macOS，需要给实际运行录音的终端或桌面应用授予麦克风权限。也可以导入已有录音。
- 首次使用原声模型会下载约 2.3 GB 的模型权重，并复用本机缓存；之后的原声推理和参考录音处理均在本机。

## 安装

### Codex

执行安装脚本，自动下载并安装到用户级技能目录，供各个项目使用：

```bash
curl -fsSL https://raw.githubusercontent.com/owl-go/text-to-speech/main/install.sh | bash -s -- --target codex
```

默认安装位置为 `~/.agents/skills/text-to-speech`。在 Codex 中输入 `$text-to-speech`，或在 `/skills` 中选择此技能。[Codex 官方安装位置与调用说明](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)

### Claude Code

执行安装脚本，安装到个人技能目录：

```bash
curl -fsSL https://raw.githubusercontent.com/owl-go/text-to-speech/main/install.sh | bash -s -- --target claude
```

默认安装位置为 `~/.claude/skills/text-to-speech`。在 Claude Code 中输入 `/text-to-speech`。两种工具使用同一份 `SKILL.md` 和 Python 脚本；`agents/openai.yaml` 只提供 Codex 的界面元数据。[Claude Code 官方技能说明](https://code.claude.com/docs/en/skills#choose-where-skills-load)

### 同时使用两者

一条命令安装到两个工具的用户级目录：

```bash
curl -fsSL https://raw.githubusercontent.com/owl-go/text-to-speech/main/install.sh | bash -s -- --target both
```

新克隆的命名音色保存在共享数据目录，可以在两个工具中按同一个名称使用。

### 项目级安装与更新

给安装脚本增加 `--project`，自动安装到该项目的 `.agents/skills/`、`.claude/skills/`：

```bash
curl -fsSL https://raw.githubusercontent.com/owl-go/text-to-speech/main/install.sh | bash -s -- --target both --project /绝对路径/项目目录
```

**更新时重新执行相同安装命令即可。** 脚本更新公开代码，保留目标目录已有的私人参考录音、实际音色配置及共享数据目录。用户级安装还会从旧版 `$CODEX_HOME/skills/text-to-speech`（默认 `~/.codex/skills/text-to-speech`）复制默认原声样本与配置；已有目标音色时保留目标配置。项目级安装不自动复制个人录音。

安装完成后，若技能没有出现在列表中，重启对应应用或会话。安装阶段只下载技能代码；依赖与模型在首次使用对应功能时准备。

也可以先下载脚本再运行：

```bash
curl -fsSL https://raw.githubusercontent.com/owl-go/text-to-speech/main/install.sh -o install-text-to-speech.sh
bash install-text-to-speech.sh --target both
```

以上命令使用 Bash，可在 macOS/Linux 终端执行；安装入口的变化不改变上文的语音功能平台要求。

## 常见使用方式

以下自然语言请求既可放在 Codex 的 `$text-to-speech` 后，也可放在 Claude Code 的 `/text-to-speech` 后。

### 1. 克隆音色：指定名称，然后开始录制

```text
克隆我的音色，命名为“讲解声”，现在开始录制，录制 15 秒。
```

助手会以这个名称保存音色，开始前有 3 秒倒计时。请在安静环境中连续说话，使用自然音量，建议录制 10–20 秒。可以朗读：

> 你好，这是我平时说话的声音。我正在录制一段参考音频，之后会用这个音色朗读不同的文字。请保留我的发音习惯和说话特点，让生成的声音尽量自然清晰。

名称已存在时保留原样本；若要替换，可以明确说：

```text
重新克隆“讲解声”，替换原来的录音，现在录制 15 秒。
```

已有授权录音也可以导入：

```text
用 /绝对路径/我的录音.wav 克隆音色，命名为“讲解声”。
```

这里的“克隆”是保存参考录音和参数，生成时提取说话人特征；不会为每个名称训练一个独立模型。仅使用本人或已取得授权的录音。

### 2. 列出当前音色

```text
列出当前音色。
```

返回云扬、云健、云希、云夏、晓晓、晓伊等预设音色，以及本机保存的命名克隆音色。`ready` 表示本机配置状态；“我的音色”未配置时会显示 `false`。列表不进行在线服务可用性检测。

### 3. 转语音

使用刚才克隆的音色：

```text
用“讲解声”说：好的，等会我去买一个葱。
```

指定正文文件、语速和输出格式：

```text
用“讲解声”把 /绝对路径/口播稿.txt 转成 MP3，语速 0.95 倍。
```

使用无需录音的预设音色：

```text
用云扬朗读：欢迎收听今天的内容。生成 WAV，语速 1.05 倍。
```

尝试情绪和精确停顿：

```text
用“讲解声”说：（生气的说）你到底（停顿3秒）有没有在听我说话？
```

情绪标记作为表演要求处理，不会读出括号或 `[angry]`。Base 克隆模型的情绪指令属于实验方式，效果需试听判断；指定停顿由音频拼接插入真实静音。详见 [情绪与停顿示例](references/emotion-and-pauses.md)。

## 直接运行脚本

以 Codex 用户级安装路径为例；Claude Code 安装用户将第一行改为 `TTS_SKILL_DIR="$HOME/.claude/skills/text-to-speech"`。

```bash
TTS_SKILL_DIR="$HOME/.agents/skills/text-to-speech"

# 指定名称后录制参考音频，默认使用系统默认麦克风
python3 "$TTS_SKILL_DIR/scripts/tts.py" clone-voice --name "讲解声" --seconds 15

# 或导入已有录音；不足 3 秒、空录音会报错
python3 "$TTS_SKILL_DIR/scripts/tts.py" clone-voice --name "讲解声" --file /绝对路径/参考录音.wav

# 列出预设和已配置的克隆音色
python3 "$TTS_SKILL_DIR/scripts/tts.py" list-voices

# 按音色名称将 UTF-8 正文转成语音
python3 "$TTS_SKILL_DIR/scripts/tts.py" generate --file /绝对路径/正文.txt --voice "讲解声" --speed 0.95 --output-dir ./tts-output

# 使用预设音色
python3 "$TTS_SKILL_DIR/scripts/tts.py" generate --text "欢迎收听今天的内容。" --voice yunyang --format wav --output-dir ./tts-output
```

录制和导入是两个可选入口，选其中一个即可；替换同名音色需加 `--replace`。`--device` 可指定 macOS 的音频设备名称或编号。输出包含音频、正文、生成参数和实际时长；原文与音色相同而只改变语速时，优先使用 `retime` 复用原始音频。

## 当前使用的模型

| 用途 | 当前模型或服务 | 运行与说明 |
| --- | --- | --- |
| 本机命名音色 / 我的音色 | [`mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit`](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit) | Qwen3-TTS 1.7B Base 的 MLX 4-bit 版本，在 Apple Silicon Mac 本机推理；使用录音提取 speaker embedding |
| 预设音色 | Microsoft Edge 在线语音服务，通过 `edge-tts` 调用 | 使用 `zh-CN-YunyangNeural` 等 voice ID；不下载本地权重，正文会发送至在线服务 |

新建克隆音色默认固定模型 revision 为 `37e955a1deb861c088ae5f3a67043185f3d1a60c`，随机种子为 42，temperature 为 0.7。参考录音统一保存为 24 kHz 单声道 PCM16。推理传入 `ref_text=None`，录音转录仅作为可选元数据，不启用 ICL 转录模式。

本项目使用 **Base 克隆模型**。官方的 **CustomVoice** 模型支持预设角色的情绪指令，例如 `Vivian`，它不会直接使用你的参考录音。本项目保持 Base 和你的音色，通过实验性的 `--instruct` 输入接入方式尝试情绪控制，不能保证与 CustomVoice 的指令遵循效果相同。[Qwen3-TTS 官方模型说明](https://github.com/QwenLM/Qwen3-TTS#released-models-description-and-download)

## 音色库与隐私

新安装默认使用 `~/.local/share/text-to-speech`，其中 `voices/` 保存命名音色，`runtime/` 保存 Python 环境，`models/` 保存模型缓存。两种工具使用同一目录。需要自定义时，为两者设置相同的 `TTS_DATA_DIR` 环境变量。

旧版本如果已存在 `~/.codex/voice-cloning`，会继续复用该目录以避免重复下载；自定义 `CODEX_HOME` 时也会检查其 `voice-cloning` 目录。`TTS_DATA_DIR` 优先于旧目录。已存在技能目录里的 `assets/voices/my-voice/profile.json` 会作为兼容配置读取；共享库中的同名配置优先。

仓库不包含私人录音、实际音色配置、生成音频或模型权重。新命名音色保存在技能目录之外，原有技能内的私人音色文件也在 `.gitignore` 中排除。

[技能指令](SKILL.md) · [音色配置与管理](references/voice-setup.md) · [情绪与停顿技巧](references/emotion-and-pauses.md)
