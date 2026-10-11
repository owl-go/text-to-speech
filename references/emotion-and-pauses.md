# 情绪与停顿用法

适用于情绪表演、`[angry]` 等标记和指定秒数的停顿。普通朗读沿用 `SKILL.md` 的调用方式。下列 `<skill-dir>` 展开为当前 Skill 目录；示例使用 0.95 倍，实际使用时沿用用户当前语速。

## 表演标记与正文

| 用户输入 | 实际朗读文字 | 控制方式 |
| --- | --- | --- |
| `（生气的说）你到底有没有在听我说话？` | `你到底有没有在听我说话？` | 用 `--instruct` 表达生气的语气 |
| `[angry]你到底有没有在听我说话？[angry]` | `你到底有没有在听我说话？` | 两个标记按同一条情绪要求处理 |
| `（生气的说）你到底（停顿3秒）有没有在听我说话？` | 分成 `你到底` 和 `有没有在听我说话？` | 两段使用同一情绪指令，之间插入 3 秒静音 |
| `大哥不要把你的东西放在电梯口呀（生气的语气），我都出不了电梯了` | 保留两句正文 | 结合语境确定表演范围；仅作用于某句时分段生成 |

由 agent 将用户的舞台指示整理成纯正文和控制参数，脚本不自动解析方括号或括号。保留朗读文字，移除明确的表演指示；不要把本来属于正文的括号内容删掉。若用户明确要求读出 `[angry]` 等字样，就按正文处理。

## 原声情绪指令：已生成过音频的实验方式

原声示例配置使用 `Qwen3-TTS-12Hz-1.7B-Base-4bit` 和 speaker embedding。官方将 Base 列为克隆模型，将 `CustomVoice` 列为支持指令控制的预设音色模型；截图中的 `speaker="Vivian"` 指向预设女声，并不使用用户录音。[Qwen 官方说明](https://github.com/QwenLM/Qwen3-TTS#released-models-description-and-download)

保持用户指定的原声模型，调用 `tts.py generate --instruct`。已安装的 MLX Base 常规 `generate()` 不传递 `instruct`，脚本仅在本次模型实例的 `_prepare_generation_inputs` 前接入指令；不改模型权重、参考录音或已安装的库，仍使用 `ref_text=None`。此方式缺少官方 Base 情绪控制保证，当前只确认能生成可解码音频，尚不能断言怒气表达可靠。用户只要求普通原声朗读时省略 `--instruct`。

已试过的生气指令：

```text
用生气的语气说。语气严厉，咬字有力，表现出压抑不住的怒火。
```

将 `你到底有没有在听我说话？` 保存为 UTF-8 文件，运行：

```bash
python3 <skill-dir>/scripts/tts.py generate --file <正文.txt> --voice my-voice --speed 0.95 --instruct "用生气的语气说。语气严厉，咬字有力，表现出压抑不住的怒火。" --output-dir <输出目录>
```

脚本把 `instruct`、`experimental: true` 和接入方式保存到 `metadata.json`，返回结果也标明实验性质。`--instruct` 仅支持 `my-voice`；Edge 音色会明确报错，避免指令被静默忽略。新情绪可以改写指令尝试，但需标明未验证，不因本例成功生成音频而声称所有情绪都有效。

编写指令时优先描述可听到的语气、重音、咬字和情绪强度。例如“语气严厉、咬字有力”比只写一个标签更明确。数字语速由 `--speed` / `--rate` / `--duration` 控制；精确停顿交给音频拼接，不靠“……”或让模型读出“停顿三秒”。交付描述可用“已用你的音色加入愤怒语气指令，效果请试听判断”。

## 指定停顿：先生成语音，再插静音

示例请求：

```text
（生气的说）你到底（停顿3秒）有没有在听我说话？
```

1. 保存两份 UTF-8 正文：`part1.txt` 为 `你到底`；`part2.txt` 为 `有没有在听我说话？`。
2. 分别用同一音色、语速和情绪指令生成，确认两次调用成功并取得返回的 `audio` 路径。

```bash
python3 <skill-dir>/scripts/tts.py generate --file <part1.txt> --voice my-voice --speed 0.95 --instruct "用生气的语气说。语气严厉，咬字有力，表现出压抑不住的怒火。" --output-dir <分句输出目录>
python3 <skill-dir>/scripts/tts.py generate --file <part2.txt> --voice my-voice --speed 0.95 --instruct "用生气的语气说。语气严厉，咬字有力，表现出压抑不住的怒火。" --output-dir <分句输出目录>
```

3. 将两个真实返回路径填入 JSON 计划文件 `pause-plan.json`：

```json
{
  "segments": [
    {"audio": "/实际输出目录/第一段/audio.mp3"},
    {"pause_seconds": 3},
    {"audio": "/实际输出目录/第二段/audio.mp3"}
  ]
}
```

4. 拼接已变速的分句，之后不再对整体做变速：

```bash
python3 <skill-dir>/scripts/join_audio.py --file <pause-plan.json> --voice my-voice --output-dir <输出目录>
```

`join_audio.py` 将分句统一解码为 44.1 kHz 单声道，在靠近指定停顿的边缘裁去多余静音，并保留 20 ms 的发音余量。3 秒停顿插入 132300 个零采样；这是插入的静音长度，听感仍可能包含分句本身的呼吸或尾音。输出目录保存 MP3/WAV、无损 `source.wav`、计划、正文及含采样数和时间位置的 `metadata.json`。以原始 WAV 和时间线核对静音；MP3 编码可能在边界引入微弱信号。

计划可包含多个音频和停顿项；相对音频路径相对于计划文件目录。`--format wav` 可直接交付 WAV。此工具负责拼接已生成的音频，不改变音色，也不重新推理模型。

更改语速且需要保留 3 秒停顿时，先对各原始分句使用 `tts.py retime`，再更新计划中的路径并重新拼接。对最终拼接音频整体使用 `retime`，会连同静音一起缩放；拼接产物的 `tempo_factor: 1.0` 指相对于已变速分句组成的整体。拼接工具不生成字幕，原声分句字幕仍只是估算稿。

## 判断完成

确认生成及拼接命令成功、最终音频可解码，再展示播放器、下载链接、音色和总时长。有指定停顿时补充插入的秒数。用户认为情绪不足时，可以改写 `instruct` 重试；没有试听证据时，把“指令已接入”与“情绪表达有效”分开报告。
