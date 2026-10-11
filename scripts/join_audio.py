#!/usr/bin/env python3
"""Join rendered speech segments with explicit pauses, after speech retiming."""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

from setup_runtime import ensure_runtime
from tts import VOICES, duration, ffmpeg, resolve_voice


def read_plan(path):
    plan = json.loads(path.read_text(encoding="utf-8"))
    items = plan.get("segments") if isinstance(plan, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("计划需要非空 segments 数组")
    segments = []
    for item in items:
        if not isinstance(item, dict) or set(item) not in ({"audio"}, {"pause_seconds"}):
            raise ValueError("每个分段仅指定 audio 或 pause_seconds")
        if "audio" in item:
            if not isinstance(item["audio"], str) or not item["audio"].strip():
                raise ValueError("audio 需要音频路径")
            audio = Path(item["audio"]).expanduser()
            audio = (path.parent / audio).resolve() if not audio.is_absolute() else audio.resolve()
            if not audio.is_file():
                raise ValueError(f"分段音频不存在：{audio}")
            segments.append({"audio": str(audio)})
        else:
            seconds = item["pause_seconds"]
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
                raise ValueError("pause_seconds 需要大于 0 的有限秒数")
            segments.append({"pause_seconds": seconds})
    if not any("audio" in item for item in segments):
        raise ValueError("计划至少需要一个语音分段")
    return segments


def trim_edge_silence(audio, sample_rate, start=False, end=False):
    """Trim only edges bordering requested pauses; keep 20 ms speech margins."""
    import numpy as np

    frame = round(sample_rate * 0.01)
    blocks = np.pad(audio, (0, (-len(audio)) % frame)).reshape(-1, frame)
    rms = np.sqrt(np.mean(blocks ** 2, axis=1))
    active = np.flatnonzero(rms > max(0.001, float(rms.max()) * 0.01))
    if not len(active):
        raise RuntimeError("分段未检测到语音，无法确定停顿边界")
    margin = round(sample_rate * 0.02)
    first = max(0, int(active[0]) * frame - margin) if start else 0
    last = min(len(audio), (int(active[-1]) + 1) * frame + margin) if end else len(audio)
    return audio[first:last]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="JSON 分段计划：audio 路径或 pause_seconds")
    parser.add_argument("--voice", default="my-voice", help="已生成分段使用的音色；本工具不生成语音")
    parser.add_argument("--format", choices=["mp3", "wav"], default="mp3")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd() / "tts-output")
    args = parser.parse_args()
    voice = resolve_voice(args.voice)
    segments = read_plan(args.file.expanduser().resolve())
    speech_texts, speech_details = {}, {}
    # Check declared voices when the input is a tts.py artifact.
    for item in segments:
        if "audio" in item:
            source_folder = Path(item["audio"]).parent
            text_path = source_folder / "text.txt"
            speech_texts[item["audio"]] = text_path.read_text(encoding="utf-8").strip() if text_path.exists() else "（音频分段）"
            metadata_path = source_folder / "metadata.json"
            if metadata_path.exists():
                prior = json.loads(metadata_path.read_text(encoding="utf-8"))
                if prior.get("voice", voice) != voice:
                    raise ValueError("分段音色与 --voice 不一致；请使用相同音色的分段")
                speech_details[item["audio"]] = {key: prior[key] for key in ("instruct", "experimental", "tempo_factor") if key in prior}
    python = ensure_runtime(audio=True)
    if Path(sys.executable).absolute() != python.absolute():
        sys.exit(subprocess.run([str(python), str(Path(__file__).resolve()), *sys.argv[1:]]).returncode)
    import numpy as np
    import soundfile as sf

    sr = 44100
    arrays, timeline = [], []
    total_samples = 0
    for i, item in enumerate(segments):
        if "audio" in item:
            decoded = subprocess.run([ffmpeg(), "-v", "error", "-i", item["audio"], "-f", "f32le", "-ac", "1", "-ar", str(sr), "pipe:1"], capture_output=True, check=True)
            audio = np.frombuffer(decoded.stdout, dtype="<f4").copy()
            if not len(audio) or not np.isfinite(audio).all():
                raise RuntimeError("分段音频为空或无法解码")
            audio = trim_edge_silence(audio, sr, start=i > 0 and "pause_seconds" in segments[i - 1], end=i + 1 < len(segments) and "pause_seconds" in segments[i + 1])
            entry = {"audio": item["audio"], "text": speech_texts[item["audio"]], "generation": speech_details.get(item["audio"], {})}
        else:
            samples = round(item["pause_seconds"] * sr)
            if samples < 1:
                raise ValueError("停顿小于一个采样点，无法插入")
            audio = np.zeros(samples, dtype=np.float32)
            entry = {"pause_seconds": samples / sr, "requested_pause_seconds": item["pause_seconds"], "samples": samples}
        entry.update({"start_seconds": total_samples / sr, "end_seconds": (total_samples + len(audio)) / sr})
        timeline.append(entry)
        arrays.append(audio)
        total_samples += len(audio)

    output_root = args.output_dir.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tts-join-", dir=output_root) as temporary:
        folder = Path(temporary)
        sf.write(str(folder / "source.wav"), np.concatenate(arrays), sr, subtype="PCM_16")
        output = folder / f"audio.{args.format}"
        encoding = ["-b:a", "192k"] if args.format == "mp3" else ["-c:a", "pcm_s16le"]
        subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-i", str(folder / "source.wav"), *encoding, str(output)], check=True)
        seconds = duration(output)
        metadata = {"voice": voice, "voice_name": VOICES[voice]["name"], "backend": "joined", "source_audio": "source.wav", "audio": output.name, "source_duration_seconds": total_samples / sr, "duration_seconds": seconds, "tempo_factor": 1.0, "sample_rate": sr, "timeline": timeline, "segments": segments, "cues": [], "subtitle_accuracy": "not_available", "note": "Speech segments were already retimed; tempo_factor is relative to the assembled source. Retiming this whole artifact also scales its pauses."}
        (folder / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "plan.json").write_text(json.dumps({"segments": segments}, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "text.txt").write_text("\n".join(speech_texts[item["audio"]] if "audio" in item else f"（停顿{item['pause_seconds']}秒）" for item in segments), encoding="utf-8")
        final = output_root / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + voice + "-joined-" + uuid.uuid4().hex[:6])
        folder.rename(final)
    print(json.dumps({"audio": str(final / output.name), "directory": str(final), "voice": VOICES[voice]["name"], "duration_seconds": round(seconds, 3), "pauses_seconds": [x["pause_seconds"] for x in timeline if "pause_seconds" in x]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"音频拼接失败：{error}", file=sys.stderr)
        sys.exit(1)
