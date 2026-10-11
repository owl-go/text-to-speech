"""Install the public skill files, preserving local voice assets on updates."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid


def public_files(source):
    names = subprocess.check_output(["git", "-C", str(source), "ls-files", "-z"]).decode("utf-8").split("\0")
    files = []
    for name in filter(None, names):
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or (source / path).is_symlink():
            raise ValueError(f"Invalid package path: {name}")
        if path.name == "profile.json" or path.suffix.lower() in (".wav", ".mp3", ".srt", ".safetensors"):
            raise ValueError(f"Private/generated assets cannot be installed from the repository: {name}")
        if (source / path).is_file():
            files.append(path)
    if Path("SKILL.md") not in files or Path("scripts/tts.py") not in files:
        raise ValueError("The source is not a text-to-speech skill checkout")
    return files


def install_to(source, destination, files, legacy=None):
    # Resolve a pre-existing linked skill folder without replacing its symlink.
    destination = destination.expanduser().resolve()
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Installation destination is not a directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tts-install-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "skill"
        if destination.exists():
            shutil.copytree(destination, staged, symlinks=True)
        else:
            staged.mkdir()
        for path in files:
            output = staged / path
            # A linked public file/directory must not redirect writes outside staging.
            for parent in reversed(output.parents):
                if parent == staged or staged not in parent.parents:
                    continue
                if parent.is_symlink():
                    raise ValueError(f"Linked package directory cannot be updated: {parent.relative_to(staged)}")
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.is_symlink():
                output.unlink()
            if output.is_dir():
                raise ValueError(f"Package file conflicts with an existing directory: {path}")
            shutil.copy2(source / path, output)
        # Keep the original user's legacy default voice usable at the new location.
        # Do not copy personal recordings into a project-scoped installation.
        if legacy is not None:
            old_voice = legacy / "assets/voices/my-voice"
            new_voice = staged / "assets/voices/my-voice"
            if (old_voice / "profile.json").is_file() and not (new_voice / "profile.json").exists():
                if new_voice.is_symlink():
                    raise ValueError("Cannot migrate a legacy voice into a linked asset directory")
                shutil.copytree(old_voice, new_voice, dirs_exist_ok=True, symlinks=True)
        backup = None
        if destination.exists():
            backup = destination.with_name(".tts-backup-" + uuid.uuid4().hex)
            destination.rename(backup)
        try:
            staged.rename(destination)
        except OSError:
            if backup is not None:
                backup.rename(destination)
            raise
        if backup is not None:
            shutil.rmtree(backup)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Downloaded Git checkout")
    parser.add_argument("--target", choices=("codex", "claude", "both"), default="codex")
    parser.add_argument("--project", type=Path, help="Project root; otherwise install for this user")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    files = public_files(source)
    root = args.project.expanduser().resolve() if args.project else Path.home()
    legacy = None if args.project else Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser() / "skills/text-to-speech"
    targets = ("codex", "claude") if args.target == "both" else (args.target,)
    installed = set()
    for target in targets:
        folder = ".agents" if target == "codex" else ".claude"
        destination = root / folder / "skills/text-to-speech"
        if destination.resolve() not in installed:
            installed.add(install_to(source, destination, files, legacy))
        command = "$text-to-speech" if target == "codex" else "/text-to-speech"
        print(f"Installed for {target}: {destination}")
        print(f"Invoke with {command} in {target}.")
    print("Private voice files preserved. Dependencies and models are prepared when used.")
    print("If the skill does not appear, restart the corresponding app/session.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Installation failed: {error}", file=sys.stderr)
        sys.exit(1)
