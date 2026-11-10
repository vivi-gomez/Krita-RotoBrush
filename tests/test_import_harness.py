"""Prueba de humo: importa el plugin con un `krita` simulado.

Ejecuta:  python3 tests/test_import_harness.py
Se puede forzar PyQt5 con:  QT=5 python3 tests/test_import_harness.py
"""

import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if os.environ.get("QT") == "5":
    sys.modules["PyQt6"] = None  # fuerza la rama PyQt5 de qt.py

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# --- Krita simulado ---------------------------------------------------------
krita = types.ModuleType("krita")


class DockWidget:
    def __init__(self, *a, **k):
        self._widget = None
        self._title = ""

    def setWindowTitle(self, t):  # noqa: N802
        self._title = t

    def setWidget(self, w):  # noqa: N802
        self._widget = w

    def widget(self):
        return self._widget


class DockWidgetFactoryBase:
    class DockPosition:
        DockRight = 0


class DockWidgetFactory(DockWidgetFactoryBase):
    def __init__(self, ident, pos, klass):
        self.id, self.klass = ident, klass


class Extension:
    def __init__(self, parent=None):
        pass


class _Instance:
    def __init__(self):
        self.factories = []
        self.actions = []

    def addDockWidgetFactory(self, f):  # noqa: N802
        self.factories.append(f)

    def activeWindow(self):  # noqa: N802
        return None

    def activeDocument(self):  # noqa: N802
        return None

    def createAction(self, *_a):  # noqa: N802
        return None


_instance = _Instance()


class Krita:
    @staticmethod
    def instance():
        return _instance


krita.DockWidget = DockWidget
krita.DockWidgetFactoryBase = DockWidgetFactoryBase
krita.DockWidgetFactory = DockWidgetFactory
krita.Extension = Extension
krita.Krita = Krita
sys.modules["krita"] = krita

sys.path.insert(0, str(ROOT / "pykrita"))

# --- arranque ---------------------------------------------------------------
_lib = ROOT / "pykrita" / "roto_brush" / "lib"
_lib.mkdir(parents=True, exist_ok=True)
_target = _lib / "libroto_brush_core.so"
_source = ROOT / "core" / "target" / "release" / "libroto_brush_core.so"
if _source.exists():
    _target.write_bytes(_source.read_bytes())

import roto_brush.qt as rbqt  # noqa: E402

app = rbqt.QApplication.instance() or rbqt.QApplication([])
import roto_brush  # noqa: E402,F401  (registra el docker)
from roto_brush.docker import RotoBrushDocker  # noqa: E402
from roto_brush.qt import QPointF  # noqa: E402

from roto_brush.controller import Controller  # noqa: E402
from roto_brush.overlay import Overlay  # noqa: E402


class _FakeCanvas:
    def zoomLevel(self):  # noqa: N802
        return 2.0


class _FakeView:
    """flake->widget: escala 2 y desplazamiento (100, 50); flake->imagen: identidad."""

    def canvas(self):
        return _FakeCanvas()

    def flakeToCanvasTransform(self):  # noqa: N802
        return rbqt.QtGui.QTransform(2, 0, 0, 2, 100, 50)

    def flakeToImageTransform(self):  # noqa: N802
        return rbqt.QtGui.QTransform(0.5, 0, 0, 0.5, 0, 0)


Controller.view = property(lambda self: _FakeView())

failures = []


def check(name, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception as e:  # noqa: BLE001
        failures.append(f"{name}: {e!r}")
        print(f"FAIL {name}: {e!r}")


def make_docker():
    d = RotoBrushDocker()
    assert d.widget() is not None, "sin widget"
    return d


def strokes_flow():
    d = make_docker()
    c = d.c
    c.brush = 12
    c.mode = 0
    c.begin_stroke(QPointF(10, 10))
    c.add_point(QPointF(12, 10))
    c.add_point(QPointF(20, 20))
    c.end_stroke()
    assert len(c.strokes) == 1 and len(c.strokes[0][2]) == 3, c.strokes
    c.mode = 1
    c.begin_stroke(QPointF(50, 50))
    c.end_stroke()
    assert len(c.strokes) == 2
    c.clear()
    assert c.strokes == []


def ui_controls():
    d = make_docker()
    d.brush.setValue(42)
    assert d.c.brush == 42
    d.modes.button(1).setChecked(True)
    d._set_mode(1)
    assert d.c.mode == 1
    d.best.setChecked(False)
    assert d.c.best is False
    d.feather.setValue(15)
    assert abs(d.c.feather - 1.5) < 1e-6
    d.smooth.setValue(25)
    assert abs(d.c.smooth - 2.5) < 1e-6


def auto_preview():
    d = make_docker()
    assert d.c.auto_preview is True
    d.auto.setChecked(False)
    assert d.c.auto_preview is False
    d.auto.setChecked(True)
    assert d.c.auto_preview is True


def stroke_editing():
    d = make_docker()
    c = d.c
    c.strokes = [
        [0, 12.0, [[10.0, 10.0], [100.0, 10.0]], -1.0],
        [1, 12.0, [[10.0, 80.0], [100.0, 80.0]], -1.0],
    ]
    c.edit_mode = True
    assert c.select_at(QPointF(50, 14)) is True
    assert c.selected == 0, c.selected
    c.set_brush(30)
    assert c.strokes[0][1] == 30.0
    c.set_selected_feather(2.5)
    assert c.strokes[0][3] == 2.5
    c.set_selected_feather(0.0)
    assert c.strokes[0][3] == -1.0
    c.delete_selected()
    assert len(c.strokes) == 1 and c.strokes[0][0] == 1
    c.edit_mode = False
    rect = (0, 0, 200, 200)
    assert c._strokes_inside(rect) is True
    assert c._strokes_inside((500, 500, 10, 10)) is False


def mask_view():
    d = make_docker()
    c = d.c
    alpha = bytes([0, 128, 255, 255])
    gray = c.engine.gray_mask(alpha, 2, 2)
    assert len(gray) == 16
    assert gray[0:4] == bytes([0, 0, 0, 255])
    assert gray[4:8] == bytes([128, 128, 128, 255])
    dim = c.engine.dim_mask(alpha, 2, 2)
    assert dim[3] == 150, dim[3]
    assert 60 <= dim[7] <= 90, dim[7]
    assert dim[11] == 0, dim[11]


def reset_params():
    d = make_docker()
    c = d.c
    c.feather = 5.0
    c.sam_weight = 15.0
    c.edit_mode = True
    c.reset_params()
    d._sync_controls()  # no debe lanzar TypeError
    assert c.feather == 1.5 and c.sam_weight == 6.0 and c.edge_smooth == 8
    assert c.edit_mode is False
    assert d.feather.value() == 15, d.feather.value()


def undo_stack():
    d = make_docker()
    c = d.c
    c.begin_stroke(QPointF(1, 1))
    c.add_point(QPointF(5, 5))
    c.end_stroke()
    c.begin_stroke(QPointF(9, 9))
    c.end_stroke()
    assert len(c.strokes) == 2
    c.undo()
    assert len(c.strokes) == 1
    c.undo()
    assert len(c.strokes) == 0
    c.undo()  # sin pila: no rompe


def layer_offset():
    d = make_docker()
    c = d.c
    rect = (50, 60, 200, 100)
    strokes = [[0, 8.0, [[150.0, 110.0], [160.0, 120.0]], -1.0]]
    local = c._to_layer(strokes, rect)
    assert local[0][2] == [[100.0, 50.0], [110.0, 60.0]], local
    assert local[0][0] == 0 and local[0][1] == 8.0


def controller_properties():
    from roto_brush.controller import Controller

    for name in ("window", "view", "document"):
        assert isinstance(Controller.__dict__[name], property), name


def dead_overlay():
    d = make_docker()
    c = d.c

    class Dead:
        def sync(self):
            raise RuntimeError("wrapped C/C++ object of type Overlay has been deleted")

        def update(self):
            raise RuntimeError("deleted")

    c.overlay = Dead()
    c._refresh()
    assert c.overlay is None
    c.set_hover(rbqt.QPointF(1, 1))
    assert c.overlay is None


def engine_loaded():
    d = make_docker()
    assert d.c.engine is not None
    assert d.c.engine.lib is not None


check("registro del docker", lambda: (_ for _ in ()).throw(AssertionError("sin factoría")) if not _instance.factories else None)
check("construir docker", make_docker)
check("trazos", strokes_flow)
check("controles", ui_controls)
check("vista previa automática", auto_preview)
def overlay_paint():
    d = make_docker()
    host = rbqt.QtWidgets.QWidget()
    host.resize(200, 200)
    host.show()
    o = Overlay(host, d.c)
    d.c.strokes = [[0, 10.0, [[1.0, 2.0], [30.0, 40.0]]], [2, 5.0, [[10.0, 10.0]]]]
    d.c.set_hover(rbqt.QPointF(50, 50))
    pm = o.grab()
    assert not pm.isNull(), "el overlay no pinta"


check("motor enlazado", engine_loaded)
check("edición de trazos", stroke_editing)
check("máscara en gris y atenuada", mask_view)
check("coordenadas con capa desplazada", layer_offset)
check("propiedades del controlador", controller_properties)
check("deshacer trazos", undo_stack)
check("overlay borrado no rompe", dead_overlay)
check("restablecer ajustes", reset_params)
def coordinates():
    from roto_brush.canvas import image_to_widget, widget_to_image

    view = _FakeView()
    img = widget_to_image(view, rbqt.QPointF(300, 250))
    assert (img.x(), img.y()) == (50.0, 50.0), img
    back = image_to_widget(view, rbqt.QPointF(100, 100))
    assert (back.x(), back.y()) == (500.0, 450.0), back


check("overlay pinta (pincel y trazos)", overlay_paint)
def mask_transform():
    from roto_brush.canvas import image_transform

    t = image_transform(_FakeView())
    p = t.map(rbqt.QPointF(100, 100))
    assert (p.x(), p.y()) == (500.0, 450.0), (p.x(), p.y())
    p0 = t.map(rbqt.QPointF(0, 0))
    assert (p0.x(), p0.y()) == (100.0, 50.0), (p0.x(), p0.y())


check("coordenadas widget <-> imagen", coordinates)
check("transformación de la máscara", mask_transform)

print(f"\n{len(failures)} fallos")
sys.exit(1 if failures else 0)
