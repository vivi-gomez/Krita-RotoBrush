"""Registro en un archivo del perfil del usuario (nada en el repositorio)."""

from pathlib import Path
import time

_LOG = Path.home() / ".local" / "share" / "krita" / "roto_brush.log"


_MAX_BYTES = 1_000_000


def _rotate() -> None:
    """Si el log crece demasiado, se guarda una copia y se empieza de cero."""
    try:
        if _LOG.exists() and _LOG.stat().st_size > _MAX_BYTES:
            backup = _LOG.with_suffix(".old.log")
            if backup.exists():
                backup.unlink()
            _LOG.rename(backup)
    except Exception:  # noqa: BLE001
        pass


def _write(text: str) -> None:
    try:
        _rotate()
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with _LOG.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
    except Exception as e:  # noqa: BLE001
        try:
            boot = Path.home() / ".local" / "share" / "krita" / "roto_brush_boot.log"
            with boot.open("a", encoding="utf-8") as f:
                f.write(f"log error: {e!r} path={_LOG}\n")
        except Exception:  # noqa: BLE001
            pass


def info(msg: str) -> None:
    _write(msg)


def error(msg: str) -> None:
    _write(f"ERROR {msg}")
