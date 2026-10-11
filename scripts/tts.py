#!/usr/bin/env python3
"""Reusable Edge/local cloned TTS with retained source audio for retiming."""
import argparse
import asyncio
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

from setup_runtime import DATA_ROOT, ensure_runtime

SKILL_ROOT = Path(__file__).resolve().parents[1]
VOICES = {
    "my-voice": {"name": "我的音色", "backend": "local", "aliases": ["自己的音色", "自己的声音", "我的声音", "原声", "原声音色"]},
    "yunyang": {"name": "云扬", "id": "zh-CN-YunyangNeural", "aliases": ["云杨"]},
    "yunjian": {"name": "云健", "id": "zh-CN-YunjianNeural"},
    "yunxi": {"name": "云希", "id": "zh-CN-YunxiNeural"},
    "yunxia": {"name": "云夏", "id": "zh-CN-YunxiaNeural"},
    "xiaoxiao": {"name": "晓晓", "id": "zh-CN-XiaoxiaoNeural"},
    "xiaoyi": {"name": "晓伊", "id": "zh-CN-XiaoyiNeural"},
}


def resolve_voice(value):
    for key, item in VOICES.items():
        if value in [key, item["name"], item.get("id"), *item.get("aliases", [])]:
            return key
    raise ValueError(f"未知音色：{value}。用 list-voices 查看可选音色。")


def positive(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("请输入大于 0 的有限数值")
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    commands.add_parser("list-voices")
    for name in ["generate", "retime"]:
        sub = commands.add_parser(name)
        if name == "generate":
            source = sub.add_mutually_exclusive_group(required=True)
            source.add_argument("--text")
            source.add_argument("--file", type=Path)
            sub.add_argument("--voice", default="yunyang")
            sub.add_argument("--language", default="chinese")
            sub.add_argument("--instruct", help="我的音色：实验性情绪/语气指令；Base 模型效果需试听判断")
        else:
            sub.add_argument("--source", type=Path, required=True)
        tempo = sub.add_mutually_exclusive_group()
        tempo.add_argument("--speed", type=positive)
        tempo.add_argument("--rate", help="例如 +5%% 或 -10%%；负数用 --rate=-10%%")
        tempo.add_argument("--duration", type=positive, help="目标秒数")
        sub.add_argument("--format", choices=["mp3", "wav"], default="mp3")
        sub.add_argument("--subtitles", action="store_true")
        sub.add_argument("--output-dir", type=Path, default=Path.cwd() / "tts-output")
    return p


def base_speed(args):
    if args.rate is not None:
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?%", args.rate):
            raise ValueError("--rate 格式为 +5% 或 -10%")
        return positive(1 + float(args.rate[:-1]) / 100)
    return args.speed if args.speed is not None else 1.05


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def duration(path):
    # Decode once to verify the output and count samples, without an ffprobe dependency.
    result = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "24000", "pipe:1"], check=True, capture_output=True)
    value = len(result.stdout) / (4 * 24000)
    if value <= 0:
        raise RuntimeError("生成的音频为空")
    return value


def tempo_filter(speed):
    factors = []
    while speed > 2:
        factors.append(2.0)
        speed /= 2
    while speed < 0.5:
        factors.append(0.5)
        speed /= 0.5
    factors.append(speed)
    return ",".join(f"atempo={x:.10f}" for x in factors)


async def generate_edge(text, voice, folder):
    import edge_tts
    source = folder / "source.mp3"
    cues = []
    communicate = edge_tts.Communicate(text, VOICES[voice]["id"], rate="+0%", boundary="SentenceBoundary")
    with source.open("wb") as output:
        async for event in communicate.stream():
            if event["type"] == "audio":
                output.write(event["data"])
            elif event["type"] == "SentenceBoundary":
                cues.append({"start": event["offset"] / 1e7, "end": (event["offset"] + event["duration"]) / 1e7, "text": event["text"]})
    return source, cues, {"backend": "edge", "subtitle_accuracy": "service_sentence_timing"}


def split_text(text):
    chunks = []
    for paragraph in re.split(r"\n\s*\n", text):
        current = ""
        for sentence in re.findall(r"[^。！？!?]+[。！？!?]*", paragraph):
            if current and len(current) + len(sentence) > 160:
                chunks.append(current.strip())
                current = ""
            while len(sentence) > 240:
                boundary = max(sentence.rfind("，", 60, 160), sentence.rfind(",", 60, 160), sentence.rfind(" ", 60, 160))
                boundary = boundary + 1 if boundary >= 60 else 160
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.append(sentence[:boundary].strip())
                sentence = sentence[boundary:]
            current += sentence
        if current.strip():
            chunks.append(current.strip())
    return chunks


def generate_clone(text, language, folder, instruct=None):
    profile_path = SKILL_ROOT / "assets/voices/my-voice/profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    reference = profile_path.parent / profile["reference_audio"]
    if not reference.is_file():
        raise RuntimeError(f"缺少自己的音色参考样本：{reference}")
    model_path = DATA_ROOT / "models" / profile["model"].split("/")[-1]
    if not (model_path / "config.json").exists():
        os.environ["HF_HUB_DISABLE_XET"] = "1"
        from huggingface_hub import snapshot_download
        print("首次准备原声模型（约 3 GB），参考录音不会上传……", flush=True)
        snapshot_download(repo_id=profile["model"], revision=profile["revision"], local_dir=str(model_path), allow_patterns=["*.json", "*.txt", "*.safetensors"], max_workers=3)
    os.environ["HF_HUB_OFFLINE"] = "1"
    from huggingface_hub import constants
    constants.HF_HUB_OFFLINE = True
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model

    mx.set_cache_limit(64 * 1024 * 1024)
    mx.set_memory_limit(7 * 1024 ** 3)
    mx.random.seed(profile["seed"])
    print("加载本机原声音色模型……", flush=True)
    model = load_model(str(model_path), strict=True)
    if instruct:
        # Base's regular generate() does not forward instruct. This is the
        # tested experimental input adapter, keeping the same speaker embedding.
        prepare = model._prepare_generation_inputs

        def prepare_with_instruction(*args, **kwargs):
            kwargs["instruct"] = instruct
            return prepare(*args, **kwargs)

        model._prepare_generation_inputs = prepare_with_instruction
        print("实验性原声情绪指令已接入；情绪效果需试听判断。", flush=True)
    arrays, cues = [], []
    elapsed = 0.0
    sr = None
    chunks = split_text(text)
    for i, chunk in enumerate(chunks):
        print(f"生成原声 {i + 1}/{len(chunks)}……", flush=True)
        pieces = []
        limit = min(2400, max(180, len(chunk) * 12))
        for result in model.generate(text=chunk, ref_audio=str(reference), ref_text=None, lang_code=language, temperature=profile["temperature"], top_k=50, top_p=1.0, repetition_penalty=1.05, max_tokens=limit, verbose=False, stream=True, streaming_interval=2.0):
            if sr is not None and sr != result.sample_rate:
                raise RuntimeError("模型返回了不一致的采样率")
            sr = result.sample_rate
            pieces.append(np.asarray(result.audio, dtype=np.float32).reshape(-1))
        if not pieces:
            raise RuntimeError("原声模型没有返回音频")
        audio = np.concatenate(pieces)
        if not len(audio) or not np.isfinite(audio).all():
            raise RuntimeError("原声模型返回无效音频")
        seconds = len(audio) / sr
        if seconds >= limit / 12.5 - 0.5:
            raise RuntimeError("原声达到生成上限，可能发生重复或截断；请缩短该段文字后重试。")
        cues.append({"start": elapsed, "end": elapsed + seconds, "text": chunk})
        arrays.append(audio)
        elapsed += seconds
        if i < len(chunks) - 1:
            arrays.append(np.zeros(round(sr * 0.3), dtype=np.float32))
            elapsed += 0.3
        mx.clear_cache()
    source = folder / "source.wav"
    sf.write(str(source), np.concatenate(arrays), sr)
    metadata = {"backend": "local", "model": profile["model"], "revision": profile["revision"], "method": profile["method"], "seed": profile["seed"], "reference_text": profile["reference_text"], "subtitle_accuracy": "estimated_segment_timing"}
    if instruct:
        metadata.update({"instruct": instruct, "experimental": True, "instruction_method": "prepend_instruction_to_base_generation_inputs"})
    return source, cues, metadata


def stamp(seconds):
    total = round(max(0, seconds) * 1000)
    return f"{total // 3600000:02}:{total // 60000 % 60:02}:{total // 1000 % 60:02},{total % 1000:03}"


def subtitles(cues, speed, audio_seconds, estimated):
    # Local captions interpolate clauses within each segment; their timing is a draft.
    entries = []
    for cue in cues:
        phrases = re.findall(r"[^，,。！？!?；;]+[，,。！？!?；;]*", cue["text"]) if estimated else [cue["text"]]
        weight = max(1, sum(len(x) for x in phrases))
        position = cue["start"] / speed
        interval = (cue["end"] - cue["start"]) / speed
        for phrase in phrases:
            end = min(audio_seconds, position + interval * len(phrase) / weight)
            if end > position:
                entries.append([position, end, phrase.strip()])
            position = end
    for i in range(len(entries) - 1):
        entries[i][1] = max(entries[i][0], min(entries[i][1], entries[i + 1][0] - 0.001))
    return "\n\n".join(f"{i + 1}\n{stamp(start)} --> {stamp(end)}\n{text}" for i, (start, end, text) in enumerate(entries)) + "\n"


def main():
    args = parser().parse_args()
    if args.command == "list-voices":
        print(json.dumps(VOICES, ensure_ascii=False, indent=2))
        return
    voice = resolve_voice(args.voice) if args.command == "generate" else None
    speed = base_speed(args)  # Validate before installing dependencies or generating anything.
    if args.command == "generate":
        if args.instruct is not None:
            args.instruct = args.instruct.strip()
            if not args.instruct:
                raise ValueError("--instruct 不能为空")
            if voice != "my-voice":
                raise ValueError("--instruct 仅用于我的音色的实验性情绪控制；预设 Edge 音色不支持此参数。")
        text = args.file.read_text(encoding="utf-8") if args.file else args.text
        text = text.strip()
        if not text:
            raise ValueError("正文不能为空")
    else:
        source_folder = args.source.resolve()
        prior = json.loads((source_folder / "metadata.json").read_text(encoding="utf-8"))
        raw_source = source_folder / prior["source_audio"]
        if not raw_source.is_file():
            raise ValueError("原始音频已丢失，无法复用变速")
    python = ensure_runtime(voice == "my-voice")
    if Path(sys.executable).absolute() != python.absolute():
        completed = subprocess.run([str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
        sys.exit(completed.returncode)
    args.output_dir = args.output_dir.expanduser().resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tts-", dir=args.output_dir) as temp:
        folder = Path(temp)
        if args.command == "generate":
            if voice == "my-voice":
                source, cues, metadata = generate_clone(text, args.language, folder, instruct=args.instruct)
            else:
                source, cues, metadata = asyncio.run(generate_edge(text, voice, folder))
            metadata.update({"voice": voice, "voice_name": VOICES[voice]["name"], "language": args.language, "cues": cues})
        else:
            import shutil
            source = folder / raw_source.name
            shutil.copyfile(raw_source, source)
            metadata = dict(prior)
            cues = metadata["cues"]
            text = (source_folder / "text.txt").read_text(encoding="utf-8")
        original_seconds = duration(source)
        if args.duration is not None:
            speed = original_seconds / args.duration
        output = folder / f"audio.{args.format}"
        command = [ffmpeg(), "-nostdin", "-v", "error", "-i", str(source), "-af", tempo_filter(speed) + ",loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "1"]
        command.extend(["-b:a", "192k"] if args.format == "mp3" else ["-c:a", "pcm_s16le"])
        subprocess.run([*command, str(output)], check=True)
        actual_seconds = duration(output)
        (folder / "text.txt").write_text(text, encoding="utf-8")
        metadata.update({"source_audio": source.name, "source_duration_seconds": original_seconds, "audio": output.name, "duration_seconds": actual_seconds, "tempo_factor": speed, "requested_duration_seconds": args.duration, "created_at": datetime.now().astimezone().isoformat()})
        if args.subtitles:
            (folder / "subtitles.srt").write_text(subtitles(cues, speed, actual_seconds, metadata["backend"] == "local"), encoding="utf-8")
        (folder / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        result_folder = args.output_dir / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + metadata["voice"] + "-" + uuid.uuid4().hex[:6])
        folder.rename(result_folder)
    summary = {"audio": str(result_folder / output.name), "directory": str(result_folder), "voice": metadata["voice_name"], "duration_seconds": round(actual_seconds, 3), "tempo_factor": round(speed, 4)}
    if metadata.get("instruct"):
        summary.update({"instruct": metadata["instruct"], "experimental": metadata.get("experimental", False)})
    if args.subtitles:
        summary["subtitles"] = str(result_folder / "subtitles.srt")
        summary["subtitle_accuracy"] = metadata["subtitle_accuracy"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (argparse.ArgumentTypeError, ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"语音生成失败：{error}", file=sys.stderr)
        sys.exit(1)
