"""Exercise installation and updates with a local Git source and isolated HOME."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from install_skill import install_to, public_files


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        (self.source / "scripts").mkdir(parents=True)
        (self.source / "assets/voices/my-voice").mkdir(parents=True)
        (self.source / "SKILL.md").write_text("---\nname: text-to-speech\n---\n")
        (self.source / "README.md").write_text("new code")
        (self.source / "scripts/tts.py").write_text("print('fixture')\n")
        (self.source / "assets/voices/my-voice/profile.example.json").write_text("{}")
        shutil.copyfile(ROOT / "scripts/install_skill.py", self.source / "scripts/install_skill.py")
        for command in (["init", "--quiet", "--initial-branch=main"], ["add", "."],
                        ["-c", "user.name=Installer Test", "-c", "user.email=installer@example.invalid",
                         "commit", "--quiet", "-m", "fixture"]):
            subprocess.run(["git", "-C", str(self.source), *command], check=True)
        self.home = self.root / "home"
        self.home.mkdir()
        # Rewire only the hard-coded repo URL to an offline fixture for bootstrap tests.
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home / ".codex"),
                        PYTHONUTF8="1", GIT_CONFIG_COUNT="1",
                        GIT_CONFIG_KEY_0=f"url.{self.source.as_uri()}.insteadOf",
                        GIT_CONFIG_VALUE_0="https://github.com/owl-go/text-to-speech.git")

    def run_installer(self, *args, bootstrap=False):
        command = [sys.executable, str(ROOT / "scripts/install_skill.py"),
                   "--source", str(self.source), *args]
        if bootstrap:
            command = ["bash", "-s", "--", *args]
        return subprocess.run(command, input=(ROOT / "install.sh").read_text() if bootstrap else None,
                              env=self.env, capture_output=True, text=True)

    def test_bootstrap_both_and_repeated_update_preserve_private_files(self):
        first = self.run_installer("--target", "both", bootstrap=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        destinations = [self.home / folder / "skills/text-to-speech"
                        for folder in (".agents", ".claude")]
        for destination in destinations:
            private = destination / "assets/voices/my-voice"
            (private / "profile.json").write_bytes(b"private config")
            (private / "reference.wav").write_bytes(b"private recording")
            (destination / "custom.txt").write_text("local file")
            (destination / "README.md").write_text("old code")
        update = self.run_installer("--target", "both", bootstrap=True)
        self.assertEqual(update.returncode, 0, update.stderr)
        for destination in destinations:
            self.assertEqual((destination / "README.md").read_text(), "new code")
            self.assertEqual((destination / "custom.txt").read_text(), "local file")
            self.assertEqual((destination / "assets/voices/my-voice/reference.wav").read_bytes(), b"private recording")
            self.assertEqual((destination / "assets/voices/my-voice/profile.json").read_bytes(), b"private config")
            self.assertEqual(list(destination.parent.glob(".tts-*")), [])

    def test_legacy_voice_migrates_without_overwriting_target(self):
        voice = self.home / ".codex/skills/text-to-speech/assets/voices/my-voice"
        voice.mkdir(parents=True)
        (voice / "profile.json").write_bytes(b"legacy profile")
        (voice / "reference.wav").write_bytes(b"legacy recording")
        result = self.run_installer("--target", "codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        migrated = self.home / ".agents/skills/text-to-speech/assets/voices/my-voice"
        self.assertEqual((migrated / "reference.wav").read_bytes(), b"legacy recording")
        (migrated / "profile.json").write_bytes(b"new local profile")
        self.assertEqual(self.run_installer().returncode, 0)
        self.assertEqual((migrated / "profile.json").read_bytes(), b"new local profile")
        self.assertTrue((voice / "reference.wav").exists())

    def test_default_bootstrap_installs_only_codex(self):
        result = self.run_installer(bootstrap=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".agents/skills/text-to-speech/SKILL.md").exists())
        self.assertFalse((self.home / ".claude").exists())

    def test_project_with_spaces_does_not_copy_personal_recording(self):
        old = self.home / ".codex/skills/text-to-speech/assets/voices/my-voice"
        old.mkdir(parents=True)
        (old / "profile.json").write_text("personal")
        project = self.root / "project with spaces"
        result = self.run_installer("--target", "both", "--project", str(project), bootstrap=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for folder in (".agents", ".claude"):
            skill = project / folder / "skills/text-to-speech"
            self.assertTrue((skill / "SKILL.md").exists())
            self.assertFalse((skill / "assets/voices/my-voice/profile.json").exists())
        self.assertFalse((self.home / ".agents").exists())

    def test_failed_swap_restores_existing_installation(self):
        destination = self.home / ".agents/skills/text-to-speech"
        destination.mkdir(parents=True)
        (destination / "SKILL.md").write_text("original")
        original_rename = Path.rename
        def fail_staged_rename(path, target):
            if path.name == "skill":
                raise OSError("simulated swap failure")
            return original_rename(path, target)
        with patch.object(Path, "rename", fail_staged_rename), self.assertRaises(OSError):
            install_to(self.source, destination, public_files(self.source))
        self.assertEqual((destination / "SKILL.md").read_text(), "original")
        self.assertEqual(list(destination.parent.glob(".tts-*")), [])

    def test_invalid_target_and_private_source_rejected(self):
        result = self.run_installer("--target", "unknown", bootstrap=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.home / ".agents").exists())
        (self.source / "assets/voices/my-voice/profile.json").write_text("private")
        subprocess.run(["git", "-C", str(self.source), "add", "."], check=True)
        with self.assertRaises(ValueError):
            public_files(self.source)


if __name__ == "__main__":
    unittest.main()
