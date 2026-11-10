"""Arranque del motor SAM 2.1 (proceso aparte con su propio Python y PyTorch)."""

import os
import subprocess
from pathlib import Path


def engine_dir():
    """Directorio del proyecto con engine/worker.py y .engine/venv."""
    env = os.environ.get("ROTO_BRUSH_ENGINE")
    if env:
        return Path(env)
    # Instalación: install.sh deja la ruta del repositorio en "engine_dir".
    try:
        marker = Path(__file__).resolve().parent / "engine_dir"
        if marker.exists():
            candidate = Path(marker.read_text().strip())
            if (candidate / "engine" / "worker.py").exists():
                return candidate
    except Exception:  # noqa: BLE001
        pass
    # Cuando el plugin se usa desde el propio repositorio.
    here = Path(__file__).resolve()
    for parent in list(here.parents)[:6]:
        if (parent / "engine" / "worker.py").exists() and (parent / ".engine" / "venv").exists():
            return parent
    return None


def start_worker(directory: Path, port: int = 8765) -> subprocess.Popen:
    python = directory / ".engine" / "venv" / "bin" / "python"
    worker = directory / "engine" / "worker.py"
    log = directory / ".engine" / "worker.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    out = log.open("ab")
    return subprocess.Popen(
        [str(python), str(worker), "--port", str(port)],
        cwd=str(directory),
        stdout=out,
        stderr=out,
        start_new_session=True,
    )
