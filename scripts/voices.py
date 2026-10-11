"""Named local voice references shared by Codex and Claude Code."""
import hashlib
import json
from pathlib import Path
import unicodedata

from setup_runtime import DATA_ROOT

SKILL_ROOT = Path(__file__).resolve().parents[1]
VOICE_ROOT = DATA_ROOT / "voices"
MY_VOICE_ALIASES = ["我的音色", "自己的音色", "自己的声音", "我的声音", "原声", "原声音色"]
DEFAULT_PROFILE = {
    "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit",
    "revision": "37e955a1deb861c088ae5f3a67043185f3d1a60c",
    "seed": 42,
    "temperature": 0.7,
    "method": "reference_audio_speaker_embedding",
    "reference_audio": "reference.wav",
    "reference_text": "",
}
PRESET_VOICES = {
    "yunyang": {"name": "云扬", "id": "zh-CN-YunyangNeural", "aliases": ["云杨"]},
    "yunjian": {"name": "云健", "id": "zh-CN-YunjianNeural"},
    "yunxi": {"name": "云希", "id": "zh-CN-YunxiNeural"},
    "yunxia": {"name": "云夏", "id": "zh-CN-YunxiaNeural"},
    "xiaoxiao": {"name": "晓晓", "id": "zh-CN-XiaoxiaoNeural"},
    "xiaoyi": {"name": "晓伊", "id": "zh-CN-XiaoyiNeural"},
}


def normalized_name(value):
    if not isinstance(value, str):
        raise ValueError("音色名称需要文字")
    name = unicodedata.normalize("NFC", value.strip())
    if not name or len(name) > 80 or any(unicodedata.category(c).startswith("C") for c in name):
        raise ValueError("音色名称需要 1–80 个可见字符")
    return name


def voice_id_for_name(value):
    name = normalized_name(value)
    if name == "my-voice" or name in MY_VOICE_ALIASES:
        return "my-voice"
    reserved = {key for key in PRESET_VOICES}
    for item in PRESET_VOICES.values():
        reserved.update([item["name"], item["id"], *item.get("aliases", [])])
    if name in reserved or name.startswith("clone-"):
        raise ValueError("请为克隆音色选择一个不与预设名称或内部 ID 重复的名称")
    return "clone-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def clone_descriptor(voice_id, profile_path):
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or not isinstance(profile.get("reference_audio"), str):
        raise ValueError(f"音色配置无效：{profile_path}")
    reference = profile_path.parent / profile["reference_audio"]
    return {
        "name": "我的音色" if voice_id == "my-voice" else normalized_name(profile.get("name", voice_id)),
        "backend": "local",
        "ready": reference.is_file(),
        "model": profile.get("model", DEFAULT_PROFILE["model"]),
        "profile_path": str(profile_path),
        "aliases": MY_VOICE_ALIASES if voice_id == "my-voice" else [],
    }


def voice_catalog():
    voices = {"my-voice": {"name": "我的音色", "backend": "local", "ready": False, "aliases": MY_VOICE_ALIASES}}
    voices.update({key: dict(item, backend="edge", ready=True) for key, item in PRESET_VOICES.items()})
    legacy = SKILL_ROOT / "assets/voices/my-voice/profile.json"
    if legacy.is_file():
        voices["my-voice"] = clone_descriptor("my-voice", legacy)
    if VOICE_ROOT.exists():
        for profile in sorted(VOICE_ROOT.glob("*/profile.json")):
            voice_id = profile.parent.name
            if voice_id != "my-voice" and not (voice_id.startswith("clone-") and len(voice_id) == 22):
                continue
            voices[voice_id] = clone_descriptor(voice_id, profile)
    return voices


VOICES = voice_catalog()


def resolve_voice(value):
    value = normalized_name(value)
    VOICES.clear()
    VOICES.update(voice_catalog())
    for key, item in VOICES.items():
        if value in [key, item["name"], item.get("id"), *item.get("aliases", [])]:
            return key
    raise ValueError(f"未知音色：{value}。用 list-voices 查看可选音色。")


def is_clone(voice):
    return VOICES[voice]["backend"] == "local"


def load_clone_profile(voice):
    item = VOICES[voice]
    if not item.get("ready"):
        raise ValueError(f"音色「{item['name']}」尚未配置，请先 clone-voice --name '{item['name']}' 录制，或通过 --file 导入参考音频。")
    path = Path(item["profile_path"])
    profile = dict(DEFAULT_PROFILE, **json.loads(path.read_text(encoding="utf-8")))
    return profile, path.parent / profile["reference_audio"]
