from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
PID_FILE = LOG_DIR / "streamlit.pid"
OUT_LOG = LOG_DIR / "streamlit.out.log"
ERR_LOG = LOG_DIR / "streamlit.err.log"


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    python_exe = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        print(f"No existe {python_exe}. Instala dependencias primero.")
        return 1

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    with OUT_LOG.open("ab") as stdout, ERR_LOG.open("ab") as stderr:
        process = subprocess.Popen(
            [
                str(python_exe),
                "-m",
                "streamlit",
                "run",
                "app/main.py",
                "--server.port",
                "8501",
                "--server.headless",
                "true",
            ],
            cwd=ROOT,
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    print(f"Streamlit iniciado con PID {process.pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
