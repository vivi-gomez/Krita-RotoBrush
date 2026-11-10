"""Prueba del recorder: sesión sintética con la imagen de referencia.

Crea una grabación como la que haría el usuario (capa = imagen EFFECTCRAFT
recortada, tres trazos verticales por cabeza/cuerpo/pies) en
tests/recordings/sesion-TEST-sim. Sirve para validar el arnés
replay_recording.py sin esperar a una sesión real de Krita.

Ejecutar:  python3 tests/test_recorder.py
"""

import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT / "tests" / "recordings" / "sesion-TEST-sim"

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["ROTO_BRUSH_RECORD"] = "1"
os.environ["ROTO_BRUSH_RECORD_SESSION"] = SESSION.name

# --- Krita simulado (mínimo para importar el plugin) -------------------------
krita = types.ModuleType("krita")


class DockWidget:
    def __init__(self, *a, **k):
        pass


class DockWidgetFactoryBase:
    class DockPosition:
        DockRight = 0


class DockWidgetFactory(DockWidgetFactoryBase):
    def __init__(self, ident, pos, klass):
        pass


class Extension:
    def __init__(self, parent=None):
        pass


class _Instance:
    def addDockWidgetFactory(self, f):  # noqa: N802
        pass

    def activeWindow(self):  # noqa: N802
        return None

    def activeDocument(self):  # noqa: N802
        return None


class Krita:
    @staticmethod
    def instance():
        return _Instance()


krita.DockWidget = DockWidget
krita.DockWidgetFactoryBase = DockWidgetFactoryBase
krita.DockWidgetFactory = DockWidgetFactory
krita.Extension = Extension
krita.Krita = Krita
sys.modules["krita"] = krita

sys.path.insert(0, str(ROOT / "pykrita"))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import roto_brush.qt as rbqt  # noqa: E402

rbqt.QApplication.instance() or rbqt.QApplication([])

from roto_brush.controller import Controller  # noqa: E402

REF = ROOT / "assets" / "Krea2_turbo_style_reference_00001_EFFECTCRAFT.png"


class FakeDoc:
    """Documento como el de Krita 6: name/width/height, SIN url()."""

    def name(self):
        return "Krea2_turbo_style_reference_00001_.png"

    def width(self):
        return 1024

    def height(self):
        return 1024


Controller.document = property(lambda self: FakeDoc())


def stroke_points(w, h):
    """Tres trazos verticales por zonas del personaje (según el alfa de ref)."""
    a = np.array(Image.open(REF).convert("RGBA"))[:, :, 3] > 127
    ys, xs = np.where(a)
    y0, y1 = ys.min(), ys.max()

    def band(f0, f1, n=24):
        ya, yb = int(y0 + (y1 - y0) * f0), int(y0 + (y1 - y0) * f1)
        m = a[ya:yb]
        yy, xx = np.where(m)
        if len(xx) == 0:
            raise SystemExit("banda vacía en la referencia")
        cx = int(xx.mean())
        return [[float(cx), float(ya + (yb - ya) * i / (n - 1))] for i in range(n)]

    return [band(0.02, 0.30), band(0.32, 0.62), band(0.72, 0.97)]


def main() -> int:
    if SESSION.exists():
        import shutil

        shutil.rmtree(SESSION)

    img = Image.open(REF).convert("RGBA")
    w, h = img.size
    arr = np.array(img)[:, :, [2, 1, 0, 3]].tobytes()  # RGBA -> BGRA

    c = Controller(ROOT / "core" / "target" / "release" / "libroto_brush_core.so")
    c.recorder.begin(c)
    assert c.recorder.dir is not None, "recorder no comenzó (¿ROTO_BRUSH_RECORD?)"
    c.source = ("fake-node", (0, 0, w, h), arr)
    c.recorder.image(c)

    for pts in stroke_points(w, h):
        c.mode = 0
        c.begin_stroke(rbqt.QPointF(*pts[0]))
        for p in pts[1:]:
            c.add_point(rbqt.QPointF(*p))
        c.end_stroke()
    c.recorder.note("fin de la sesión sintética")

    jsonl = (SESSION / "strokes.jsonl").read_text(encoding="utf-8")
    lines = [l for l in jsonl.splitlines() if '"ev": "strokes"' in l]
    assert len(lines) == 3, f"esperaba 3 eventos de trazos, hay {len(lines)}"
    import json

    last = json.loads(lines[-1])
    assert last["n"] == 3 and len(last["strokes"]) == 3, last["n"]
    total_pts = sum(len(s[2]) for s in last["strokes"])
    assert total_pts == 72, total_pts
    assert (SESSION / "layer.bgra").stat().st_size == w * h * 4
    meta = json.loads((SESSION / "meta.json").read_text(encoding="utf-8"))
    assert meta["rect"] == [0, 0, w, h], meta.get("rect")
    assert meta.get("document") == "Krea2_turbo_style_reference_00001_.png", meta
    assert meta.get("width") == 1024 and "url" not in meta, meta
    print(f"OK sesión sintética en {SESSION} ({total_pts} puntos, 3 trazos)")
    print("Ahora:  .engine/venv/bin/python tests/replay_recording.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
