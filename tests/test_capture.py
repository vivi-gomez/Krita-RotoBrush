"""Prueba del captor de gestos sin Krita (PyQt5 + eventos de mentira).

Cubre el fallo de la sesión 9: con tableta el mismo gesto llegaba dos veces
(TabletPress y su eco de ratón) y cada repetición abría un trazo fantasma de
un solo punto. Ejecutar: python3 tests/test_capture.py
"""

import importlib.util
import os
import sys
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
# RB_SRC permite pasarle la COPIA INSTALADA en Krita y comprobar que allí
# dentro está el código arreglado, no solo en el repo.
SRC = Path(os.environ.get("RB_SRC", ROOT / "pykrita" / "roto_brush"))
print(f"Analizando: {SRC}")

pkg = types.ModuleType("rb")
pkg.__path__ = [str(SRC)]
sys.modules["rb"] = pkg


def load(name):
    spec = importlib.util.spec_from_file_location(f"rb.{name}", SRC / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"rb.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


log = load("log")
qt = load("qt")
canvas = load("canvas")

QtCore = qt.QtCore
QEvent, QPointF, Qt = qt.QEvent, qt.QPointF, qt.Qt
QPoint = QtCore.QPoint
QRect = QtCore.QRect if hasattr(QtCore, "QRect") else QtCore.QRectF

T = qt.event_type
LEFT = qt.mouse_button("LeftButton")
PRESS, MOVE, RELEASE = T("MouseButtonPress"), T("MouseMove"), T("MouseButtonRelease")
TPRESS, TMOVE, TRELEASE = T("TabletPress"), T("TabletMove"), T("TabletRelease")


class Ev:
    """QEvent de mentira con lo justo que lee Capture."""

    def __init__(self, t, x=20.0, y=30.0, buttons=LEFT, button=LEFT, pressure=1.0):
        self._t, self._x, self._y = t, x, y
        self._buttons, self._button, self._pressure = buttons, button, pressure

    def type(self):
        return self._t

    def position(self):
        return QPointF(self._x, self._y)

    def pos(self):
        return QPoint(int(self._x), int(self._y))

    def buttons(self):
        return self._buttons

    def button(self):
        return self._button

    def pressure(self):
        return self._pressure

    def modifiers(self):
        return Qt.NoModifier


class Wiget:
    """Widget de mentira: el lienzo."""

    def __init__(self):
        self._rect = QRect(0, 0, 200, 200)

    def parent(self):
        return None

    def rect(self):
        return self._rect


class Ctrl:
    """Controlador de mentira que apunta lo que le piden."""

    def __init__(self, neutral=True):
        self.document = None
        self.view = None
        self.neutral = neutral
        self.begins = 0
        self.ends = 0
        self.points = []

    def tool_is_neutral(self):
        return self.neutral

    def set_hover(self, pos):
        pass

    def begin_stroke(self, img):
        self.begins += 1

    def add_point(self, img):
        self.points.append(img)

    def end_stroke(self):
        self.ends += 1


def make(neutral=True):
    c = Ctrl(neutral)
    cap = canvas.Capture(c)
    cap.active = True
    cap.target = Wiget()
    cap._inside = lambda obj: True
    canvas.widget_to_image = lambda view, pos, size: QPointF(pos.x(), pos.y())
    return cap, c


ok = 0
fails = []


def check(name, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  OK   {name}")
    else:
        fails.append(name)
        print(f"  FALLA {name} {extra}")


print("gesto de tableta con eco de ratón (el fallo de la sesión 9)")
cap, c = make()
seq = [
    Ev(TPRESS, 20, 30), Ev(PRESS, 20, 30),                        # press + eco
    Ev(TMOVE, 40, 30), Ev(MOVE, 40, 30),                          # move + eco
    Ev(TMOVE, 60, 40), Ev(MOVE, 60, 40),
    Ev(TRELEASE, 60, 40), Ev(RELEASE, 60, 40),                    # release + eco
]
for e in seq:
    cap._handle(e, cap.target)
check("un solo trazo abierto", c.begins == 1, f"begins={c.begins}")
check("un solo trazo cerrado", c.ends == 1, f"ends={c.ends}")
check("los puntos del trazo se guardan", len(c.points) == 2, f"puntos={len(c.points)}")

print("gesto de ratón a secas sigue funcionando")
cap, c = make()
for e in [Ev(PRESS), Ev(MOVE, 40, 40), Ev(RELEASE, 40, 40)]:
    cap._handle(e, cap.target)
check("un trazo de ratón", c.begins == 1 and c.ends == 1, f"{c.begins}/{c.ends}")

print("dos gestos seguidos = dos trazos")
cap, c = make()
for e in [Ev(TPRESS), Ev(TMOVE, 40, 40), Ev(TRELEASE, 40, 40),
          Ev(TPRESS, 80, 80), Ev(TMOVE, 90, 90), Ev(TRELEASE, 90, 90)]:
    cap._handle(e, cap.target)
check("dos trazos abiertos y cerrados", c.begins == 2 and c.ends == 2, f"{c.begins}/{c.ends}")

print("soltar fuera del lienzo no atrapa la bandera")
cap, c = make()
cap._handle(Ev(TPRESS), cap.target)
fuera = Ev(TRELEASE, 500, 500)  # fuera del rect del lienzo
check("la suelta de fuera se reenvía a Krita", cap._handle(fuera, cap.target) is False)
cap._handle(Ev(TPRESS, 100, 100), cap.target)
check("el siguiente trazo SÍ abre", c.begins == 2, f"begins={c.begins}")
check("el trazo huérfano se cerró", c.ends == 1, f"ends={c.ends}")

print("move y release sin press no inventan trazos")
cap, c = make()
check("move suelto reenviado", cap._handle(Ev(MOVE), cap.target) is False)
check("release suelto reenviado", cap._handle(Ev(RELEASE), cap.target) is False)
check("nada abrió ni cerró", c.begins == 0 and c.ends == 0)

print("con la herramienta ocupada (pan/zoom) no se dibuja")
cap, c = make(neutral=False)
check("press reenviado a Krita", cap._handle(Ev(TPRESS), cap.target) is False)
check("release reenviado a Krita", cap._handle(Ev(TRELEASE), cap.target) is False)
check("ni un trazo", c.begins == 0 and c.ends == 0)

print("stop() limpia el estado")
cap, c = make()
cap._handle(Ev(TPRESS), cap.target)
cap.target = None
cap.stop()
check("bandera abajo tras stop", cap._stroke_open is False)

print()
print(f"{ok} comprobaciones OK" + (f", FALLAN: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
