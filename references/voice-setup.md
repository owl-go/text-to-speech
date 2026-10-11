# 音色配置与管理

本 Skill 的脚本同时用于 Codex 和 Claude Code。克隆音色保存的是用户授权的参考录音与参数，生成时提取 speaker embedding，不训练独立模型。

## 命名后录制

用户明确要求开始录制，并已给出名称时运行：

```bash
python3 <skill-dir>/scripts/tts.py clone-voice --name "讲解声" --seconds 15
```

先准备基础运行环境，再向用户说明名称、时长和 3 秒倒计时；脚本在倒计时后开始录音，完成后自动保存。默认录制 15 秒，至少 3 秒，建议 10–20 秒清晰、自然的连续说话。`--device` 接收 macOS 默认麦克风的 `default`、设备名称或编号；录制使用 FFmpeg AVFoundation 的仅音频输入，不开启摄像头。[FFmpeg 设备说明](https://ffmpeg.org/ffmpeg-devices.html#avfoundation)

麦克风现场录制目前只支持 macOS；录音失败时报告实际错误，检查运行应用的系统麦克风权限和输入设备。不要因用户只要求技能维护、列表或生成而录音。默认保留同名样本；用户明确要求重录或替换时加 `--replace`，成功采集和验证新样本后再替换。

## 导入已有授权录音

```bash
python3 <skill-dir>/scripts/tts.py clone-voice --name "讲解声" --file <参考录音.wav>
```

`--file` 跳过麦克风，支持 FFmpeg 可解码的音频。脚本转换为 24 kHz 单声道 PCM16，检查时长及音量，然后登记名称。导入不下载原声模型；首次转语音才加载或准备模型。导入也遵循同名保护，明确替换时传 `--replace`。

## 列出及使用

```bash
python3 <skill-dir>/scripts/tts.py list-voices
python3 <skill-dir>/scripts/tts.py generate --voice "讲解声" --file <正文.txt> --output-dir <输出目录>
```

列表包括预设和命名克隆音色，`backend` 为 `edge` 或 `local`，`ready` 表示本机配置状态，不是在线可用性检测。克隆音色也返回模型和配置路径。生成可用登记名称或内部 ID；名称不会直接作为文件夹路径，中文名称可直接使用。预设音色名称保留，克隆时另选名称。

若用户把新样本命名为“我的音色”或 `my-voice`，会登记为默认原声；之后“我的声音、自己的音色、原声”等说法都选择它。用户指定其他名称时沿用该名称，不擅自替换默认原声。

## 共享存储与旧版兼容

`TTS_DATA_DIR` 指定数据目录。未指定时，新安装使用 `~/.local/share/text-to-speech`；已有旧版 `~/.codex/voice-cloning`（或自定义 `CODEX_HOME` 中的对应目录）则复用旧缓存。Codex 与 Claude Code 使用相同数据目录，可互相读取登记音色。

`voices/<内部ID>/reference.wav` 为样本，同目录 `profile.json` 为参数；录音及配置不上传。发布代码只包含 `assets/voices/my-voice/profile.example.json`。模型、revision、种子等默认参数在 `scripts/voices.py` 中定义；与示例配置对应。

旧版“我的音色”仍可手动配置：把本人或授权参考录音放入 Skill 的 `assets/voices/my-voice/reference.wav`，将同目录 `profile.example.json` 复制成 `profile.json`。共享库中的默认原声优先于这份旧配置。安装、迁移或更新 Skill 时保留旧录音与实际配置。

## 模型与推理

本机原声默认使用 `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit`，要求 Apple Silicon Mac。推理保持 `ref_text=None`；`reference_text` 可留空，仅保存为元数据，不启用 ICL。具体模型、固定 revision 和情绪边界见仓库 `README.md` 的“当前使用的模型”。
