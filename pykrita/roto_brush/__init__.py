"""Roto Brush para Krita 5 y 6."""

import os
import pathlib
import traceback


def _boot(msg: str) -> None:
    """Registro mínimo de arranque (si falla la carga, esto lo deja escrito)."""
    try:
        p = pathlib.Path.home() / ".local" / "share" / "krita" / "roto_brush_boot.log"
        with p.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:  # noqa: BLE001
        pass


_boot(f"init eventtest={os.environ.get('ROTO_BRUSH_EVENTTEST')}")

try:
    from krita import DockWidgetFactory, DockWidgetFactoryBase, Krita

    from . import log
    from .docker import RotoBrushDocker

    Krita.instance().addDockWidgetFactory(
        DockWidgetFactory(
            "rotoBrush",
            DockWidgetFactoryBase.DockPosition.DockRight,
            RotoBrushDocker,
        )
    )
    _boot("docker registrado")
    log.info("docker registrado")

    if any(os.environ.get(k) for k in ("ROTO_BRUSH_EVENTTEST", "ROTO_BRUSH_DUMP", "ROTO_BRUSH_SELFTEST")):
        _auto = RotoBrushDocker()  # solo para pruebas automáticas
        _boot("docker de prueba creado")
except Exception:  # noqa: BLE001
    _boot(traceback.format_exc())
