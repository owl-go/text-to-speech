"""Capture or import a named reference; no model training or audio upload."""
from array import array
from datetime import datetime
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import wave

from voices import DEFAULT_PROFILE, MY_VOICE_ALIASES, VOICE_ROOT, normalized_name, voice_catalog, voice_id_for_name


def validate_clone_request(name, seconds, source, replace):
    name = normalized_name(name)
    voice_id = voice_id_for_name(name)
    if not math.isfinite(seconds) or seconds < 3:
        raise ValueError("录制时长至少 3 秒；建议 10–20 秒")
    existing = voice_catalog().get(voice_id, {})
    if existing.get("profile_path") and not replace:
        raise ValueError(f"音色「{name}」已存在；明确要求重新录制时才使用 --replace")
    if source is not None and not source.expanduser().is_file():
        raise ValueError(f"参考音频不存在：{source}")
    if source is None and sys.platform != "darwin":
        raise ValueError("麦克风录制目前支持 macOS；其他系统可通过 --file 导入已有参考音频")
    return name, voice_id


def capture_command(executable, destination, seconds, device):
    return [executable, "-nostdin", "-v", "error", "-f", "avfoundation", "-i", f":{device}", "-t", str(seconds), "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(destination)]


def validate_reference(path):
    with wave.open(str(path)) as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 24000:
            raise RuntimeError("参考音频必须是 24 kHz 单声道 PCM16")
        seconds = wav.getnframes() / wav.getframerate()
        samples = array("h", wav.readframes(wav.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    if seconds < 3:
        raise ValueError("参考音频不足 3 秒，请重新录制更长的样本")
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768
    if rms < 0.001:
        raise ValueError("录音为空或声音过小，请检查麦克风权限和输入设备后重试")
    return seconds


def clone_voice(name, seconds, source, device, replace, executable):
    name, voice_id = validate_clone_request(name, seconds, source, replace)
    if voice_id == "my-voice" or name in MY_VOICE_ALIASES:
        name = "我的音色"
    VOICE_ROOT.mkdir(parents=True, exist_ok=True)
    destination = VOICE_ROOT / voice_id
    with tempfile.TemporaryDirectory(prefix=".capture-", dir=VOICE_ROOT) as temporary:
        folder = Path(temporary)
        reference = folder / "reference.wav"
        if source is None:
            print(f"音色「{name}」：3 秒后开始录制 {seconds:g} 秒，请用自然语气连续说话。", flush=True)
            for countdown in (3, 2, 1):
                print(countdown, flush=True)
                time.sleep(1)
            print("开始录制……", flush=True)
            command = capture_command(executable, reference, seconds, device)
        else:
            command = [executable, "-nostdin", "-v", "error", "-i", str(source.expanduser().resolve()), "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(reference)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            detail = result.stderr.strip()[-1500:]
            hint = "检查 macOS 麦克风权限以及 --device 指定的输入设备。" if source is None else "检查参考音频是否可解码。"
            raise RuntimeError(f"音色样本采集失败。{hint}\n{detail}")
        actual_seconds = validate_reference(reference)
        profile = dict(DEFAULT_PROFILE, name=name, voice_id=voice_id, duration_seconds=actual_seconds, created_at=datetime.now().astimezone().isoformat())
        (folder / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        # Recheck after capture: another process may have saved this name meanwhile.
        backup = None
        if destination.exists():
            if not replace:
                raise ValueError(f"音色「{name}」已被其他操作保存；本次样本未覆盖它")
            backup = VOICE_ROOT / (".backup-" + uuid.uuid4().hex)
            destination.rename(backup)
        try:
            folder.rename(destination)
        except OSError:
            if backup is not None:
                backup.rename(destination)
            raise
        if backup is not None:
            shutil.rmtree(backup)
    return {"voice": voice_id, "voice_name": name, "reference_audio": str(destination / "reference.wav"), "profile": str(destination / "profile.json"), "duration_seconds": round(actual_seconds, 3), "model": profile["model"], "next_step": f"generate --voice '{name}' --file <正文.txt>"}
