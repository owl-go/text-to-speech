# 原声音色配置

发布包提供脚本与示例参数，不包含参考录音、个人音色配置、模型权重或生成音频。预设 Edge 音色可以直接使用；原声需 Apple Silicon Mac 和本人或已取得授权的录音。

1. 将清晰的参考录音保存为 Skill 目录下的 `assets/voices/my-voice/reference.wav`。
2. 将同目录 `profile.example.json` 复制为 `profile.json`。保留模型、revision 和方法；`reference_audio` 指向本机录音，`reference_text` 可留空。
3. 按 `SKILL.md` 调用 `--voice my-voice`。首次使用会准备持久 Python 环境及模型，后续复用；录音不上传。

脚本使用 speaker embedding，传入 `ref_text=None`；`reference_text` 只作元数据，不用于 ICL。`.gitignore` 排除了录音、实际配置与生成音频，分享时只包含 `profile.example.json`。已有个人配置时直接复用，安装更新时保留这些本机文件。
