"""Voice-library workflows without microphone access or model downloads.

Run with the prepared runtime: python -m unittest discover -s tests -v
"""
from array import array
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import clone_voice
import voices
from tts import ffmpeg


def write_sample(path, seconds=3.2, amplitude=8000):
    # Non-speech fixture, used only to exercise audio validation/transcoding.
    samples = array("h", (int(amplitude * math.sin(i * 2 * math.pi * 220 / 48000))
                          for i in range(round(seconds * 48000))))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        output.writeframes(samples.tobytes())


class VoiceLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / "shared/voices"
        for module, name, value in ((voices, "VOICE_ROOT", self.library),
                                    (clone_voice, "VOICE_ROOT", self.library),
                                    (voices, "SKILL_ROOT", self.root / "skill")):
            self.enterContext(patch.object(module, name, value))
        self.source = self.root / "input.wav"
        write_sample(self.source)

    def save(self, name="讲解声", source=None, replace=False):
        return clone_voice.clone_voice(name, 15, source or self.source,
                                       "default", replace, ffmpeg())

    def test_import_list_resolve_and_share_between_installations(self):
        result = self.save()
        descriptor = voices.voice_catalog()[result["voice"]]
        self.assertEqual(descriptor["name"], "讲解声")
        self.assertTrue(descriptor["ready"])
        self.assertEqual(voices.resolve_voice("讲解声"), result["voice"])
        self.assertEqual(voices.resolve_voice(result["voice"]), result["voice"])
        profile, reference = voices.load_clone_profile(result["voice"])
        self.assertEqual(profile["model"], voices.DEFAULT_PROFILE["model"])
        with wave.open(str(reference)) as wav:
            self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getsampwidth()),
                             (24000, 1, 2))
        env = dict(os.environ, TTS_DATA_DIR=str(self.library.parent), PYTHONUTF8="1")
        for host in ("codex", "claude"):
            scripts = self.root / host / "scripts"
            shutil.copytree(SCRIPTS, scripts, ignore=shutil.ignore_patterns("__pycache__"))
            output = subprocess.check_output([sys.executable, str(scripts / "tts.py"),
                                              "list-voices"], env=env, text=True)
            self.assertEqual(json.loads(output)[result["voice"]]["name"], "讲解声")

    def test_duplicate_and_failed_replace_preserve_original(self):
        result = self.save()
        path = Path(result["reference_audio"])
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "已存在"):
            self.save()
        for seconds, amplitude in ((1, 8000), (3.2, 0)):
            invalid = self.root / "invalid.wav"
            write_sample(invalid, seconds, amplitude)
            with self.assertRaises(ValueError):
                self.save(source=invalid, replace=True)
            self.assertEqual(path.read_bytes(), original)
        replacement = self.root / "replacement.wav"
        write_sample(replacement, amplitude=14000)
        updated = self.save(source=replacement, replace=True)
        self.assertEqual(updated["voice"], result["voice"])
        self.assertNotEqual(path.read_bytes(), original)
        self.assertEqual(list(self.library.glob(".backup-*")), [])

    def test_default_aliases_and_legacy_compatibility(self):
        legacy = voices.SKILL_ROOT / "assets/voices/my-voice"
        legacy.mkdir(parents=True)
        shutil.copyfile(self.source, legacy / "reference.wav")
        (legacy / "profile.json").write_text(json.dumps(voices.DEFAULT_PROFILE))
        self.assertTrue(voices.voice_catalog()["my-voice"]["ready"])
        with self.assertRaises(ValueError):
            self.save("我的音色")
        result = self.save("我的声音", replace=True)
        self.assertEqual(result["voice"], "my-voice")
        self.assertEqual(voices.resolve_voice("原声"), "my-voice")
        self.assertTrue(voices.voice_catalog()["my-voice"]["profile_path"].startswith(str(self.library)))

    def test_invalid_names_and_unknown_voice_do_not_create_library(self):
        for name in ("", "云扬", "yunyang", "clone-id", "bad\nname"):
            with self.assertRaises(ValueError):
                self.save(name)
        with self.assertRaises(ValueError):
            voices.resolve_voice("未登记的音色")
        self.assertFalse(self.library.exists())

    def test_record_countdown_and_audio_only_capture_using_mock(self):
        # Normalize before mocking subprocess, to avoid invoking hardware.
        normalized = self.root / "normalized.wav"
        subprocess.run([ffmpeg(), "-v", "error", "-i", str(self.source),
                        "-ar", "24000", str(normalized)], check=True)
        def capture(command, **kwargs):
            self.assertEqual(command[command.index("-i") + 1], ":default")
            self.assertIn("avfoundation", command)
            self.assertIn("-vn", command)
            shutil.copyfile(normalized, command[-1])
            return subprocess.CompletedProcess(command, 0, "", "")
        with patch.object(sys, "platform", "darwin"), \
                patch.object(clone_voice.time, "sleep") as sleep, \
                patch.object(clone_voice.subprocess, "run", side_effect=capture) as run:
            result = clone_voice.clone_voice("录音测试", 15, None, "default", False, ffmpeg())
        self.assertEqual(sleep.call_count, 3)
        self.assertEqual(run.call_count, 1)
        self.assertTrue(Path(result["reference_audio"]).exists())


if __name__ == "__main__":
    unittest.main()
