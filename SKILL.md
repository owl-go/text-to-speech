---
name: text-to-speech
description: "把文字、口播稿或旁白生成可试听的 MP3/WAV，支持语速、目标时长、情绪语气和指定停顿。用户要文字转语音、生成配音、试听预设音色，或用我的音色朗读时使用；原声需要用户授权的本机参考样本，情绪控制为实验方式。"
---

# 文字转语音

将用户提供的文字保存为 UTF-8 文件，再调用 `scripts/tts.py`。沿用本会话已经选择的音色、语速；没有选择时默认云扬、1.05 倍速度。保留原文，只有明确要求改稿时才修改。缺少正文时先取得正文。

发布包不含私人参考录音和音色配置。使用“我的音色”前，按 [原声音色配置](references/voice-setup.md) 在本机配置授权样本；已有配置时直接复用。

## 音色选择

| 用户说法 | `--voice` | 生成方式 |
| --- | --- | --- |
| 我的音色、自己的音色、我的声音、原声 | `my-voice` | 本机 Qwen3-TTS，使用已保存的用户录音参考 |
| 云扬、云杨 | `yunyang` | Microsoft Edge 男声 |
| 云健 | `yunjian` | Microsoft Edge 男声 |
| 云希 | `yunxi` | Microsoft Edge 男声 |
| 云夏 | `yunxia` | Microsoft Edge 男声 |
| 晓晓 | `xiaoxiao` | Microsoft Edge 女声 |
| 晓伊 | `xiaoyi` | Microsoft Edge 女声 |

`list-voices` 可列出选择，也支持表中的中文名和对应 Edge voice ID。用户要求试听时生成一小段实际音频；不要仅描述音色。未知音色会报错，不能自动换成另一音色。

## 调用

下面路径相对于本 Skill 所在目录；执行时将它们展开为绝对路径。直接用 `python3` 调用，脚本会复用持久 Python 环境，第一次需要相应功能时安装依赖。

```bash
python3 <skill-dir>/scripts/tts.py list-voices
python3 <skill-dir>/scripts/tts.py generate --file <正文.txt> --voice my-voice --speed 1.05 --output-dir <输出目录>
python3 <skill-dir>/scripts/tts.py generate --file <正文.txt> --voice yunyang --rate +5% --output-dir <输出目录>
python3 <skill-dir>/scripts/tts.py generate --file <正文.txt> --voice my-voice --duration 60 --format mp3 --output-dir <输出目录>
```

- `--speed` 是速度倍率，`--rate` 是百分比，`--duration` 是目标秒数；三者互斥。未指定时速度为 1.05。要求“再快/再慢一点”时在上次值上调整；目标时长可能导致不自然的速度，结合实际倍率说明。
- 默认输出 MP3，也可 `--format wav`。每次生成独立目录，包含音频、正文、参数与实际时长。`--subtitles` 另外输出 SRT：预设音色使用服务的句子时间，原声音色只有按分段估算的字幕初稿，不能称为精确逐字字幕。
- 预设音色会把正文发送至 Edge 在线语音服务；原声音色推理在本机，参考录音不上传。原声需要 Apple Silicon Mac；现有模型和持久环境复用，无须每次下载。
- 原声参考样本位于 `assets/voices/my-voice/reference.wav`，参数位于同目录 `profile.json`。它是私人的参考音频克隆配置，并非独立训练的音色模型；未经用户要求不要打包分享此资产。新增别人的音色须取得其授权和对应样本，不能复用当前样本冒充。
- 已验证的原声路径使用 speaker embedding，传入 `ref_text=None`。本机测试中 ICL 转录模式出现重复乱读，因此脚本将参考转录仅保存为元数据。不要改回 ICL，除非重新验证输出。
- `--language` 默认 `chinese`；其他语言须显式选择。若克隆失败，说明失败原因并保留用户指定音色，不自动退回预设音色。

## 情绪和停顿

用户要求生气等情绪、使用 `[angry]` / `（生气的说）` 标记，或指定 `（停顿3秒）` 时，阅读 [情绪与停顿用法](references/emotion-and-pauses.md)。将表演标记与实际朗读文字分开；只有用户要求把标记读出来时，才将标记作为正文。

`--instruct` 让当前原声 Base 模型实验性接收语气指令，沿用用户音色和 `ref_text=None`。音频生成、解码成功不等于情绪效果已验证；交付时说明加入了何种指令，效果交由试听判断。精确停顿用 `scripts/join_audio.py` 在分句变速之后插入静音。

## 完成与复用

脚本返回 `audio`、`duration_seconds` 和 `tempo_factor`。确认命令成功且音频可解码，再用 `![试听](绝对音频路径)` 展示播放器；同时给下载链接、实际时长和所选音色。只在真实生成过音频后报告成功。

需要更改语速且原文、音色相同，优先用 `retime` 复用原始音频，避免再次运行克隆：

```bash
python3 <skill-dir>/scripts/tts.py retime --source <上次输出的目录> --speed 1.15 --output-dir <输出目录>
python3 <skill-dir>/scripts/tts.py retime --source <上次输出的目录> --duration 60 --output-dir <输出目录>
```

`retime` 的速度始终相对于原始生成音频，避免多次变速造成失真。用户仅想创建或列出 Skill 时，不擅自录制麦克风或生成整篇配音。
