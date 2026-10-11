"""Install only the dependencies needed for the selected TTS backend."""
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

DATA_ROOT = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "voice-cloning"
RUNTIME = DATA_ROOT / "runtime"


def ensure_runtime(clone=False):
    if clone and (sys.platform != "darwin" or platform.machine() != "arm64"):
        raise RuntimeError("我的音色需要 Apple Silicon Mac；请在支持的本机运行。")
    python = RUNTIME / "bin" / "python"
    if not python.exists():
        candidates = [
            shutil.which("python3.12"),
            str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"),
            sys.executable,
        ]
        executable = next((p for p in candidates if p and Path(p).exists()), None)
        RUNTIME.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([executable, "-m", "venv", str(RUNTIME)], check=True)
    modules = ["edge_tts", "imageio_ffmpeg"] + (["mlx_audio", "soundfile", "sentencepiece"] if clone else [])
    probe = "import importlib.util,sys;sys.exit(not all(importlib.util.find_spec(x) for x in " + repr(modules) + "))"
    if subprocess.run([str(python), "-c", probe]).returncode:
        packages = ["edge-tts==7.2.8", "imageio-ffmpeg==0.6.0"]
        if clone:
            packages.extend(["mlx-audio[stt]==0.5.8", "mlx==0.32.3", "mlx-metal==0.32.3", "soundfile==0.14.0", "sentencepiece==0.2.2", "transformers==5.19.0", "huggingface-hub==2.2.0"])
        print("准备持久语音环境……", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", *packages], check=True)
    return python


if __name__ == "__main__":
    print(ensure_runtime("--clone" in sys.argv))
