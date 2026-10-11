# text-to-speech

用于 Codex 的文字转语音技能，支持 Edge 预设音色及本机 Qwen3-TTS 原声克隆，输出 MP3/WAV，提供语速调整、实验性情绪指令和指定秒数停顿。

## 安装

将仓库克隆到 Codex 的技能目录；若 `CODEX_HOME` 已自定义，请相应调整路径：

```bash
git clone https://github.com/owl-go/text-to-speech.git ~/.codex/skills/text-to-speech
```

如果该目录已有技能或个人音色配置，先保留本机文件，再将仓库的说明和脚本更新到该目录。

## 使用

在 Codex 中调用 `$text-to-speech`，并提供要朗读的文字，例如：

- 用云扬朗读这段文字，语速 1.05 倍。
- 用我的音色说：好的，等会我去买一个葱。
- 用我的音色说：（生气的说）你到底（停顿3秒）有没有在听我说话？

[技能说明](SKILL.md) · [情绪与停顿示例](references/emotion-and-pauses.md) · [原声音色配置](references/voice-setup.md)

预设音色将正文发送至 Edge 在线语音服务。原声推理在本机，要求 Apple Silicon Mac，并需先配置已授权的参考录音。Base 原声情绪指令为实验方式，生成成功不代表情绪效果已验证。

仓库不包含私人录音、实际音色配置、生成音频或模型权重；只提供空白配置模板。
