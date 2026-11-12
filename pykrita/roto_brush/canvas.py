"""Conversión de coordenadas y captura de trazos sobre el lienzo."""

from . import log
from .qt import (
    QApplication,
    QEvent,
    QObject,
    QPointF,
    QtWidgets,
    event_type,
    key_code,
    keyboard_modifier,
    mouse_button,
)


PRESS = (event_type("MouseButtonPress"),)
MOVE = (event_type("MouseMove"),)
RELEASE = (event_type("MouseButtonRelease"),)
TABLET_PRESS = (event_type("TabletPress"),)
TABLET_MOVE = (event_type("TabletMove"),)
TABLET_RELEASE = (event_type("TabletRelease"),)


def event_pos(ev):
    """Posición local del evento (Qt5 y Qt6)."""
    return ev.position() if hasattr(ev, "position") else QPointF(ev.pos())


def find_canvas_widget(window, fallback_widget=None):
    """El widget del lienzo: hijo del viewport con su mismo tamaño y posición.

    Las transformaciones de View usan el espacio de ese widget, no el del
    QMdiArea ni el del área de desplazamiento que lo contiene.
    """
    qwin = None
    try:
        if window is not None:
            qwin = window.qwindow()
    except Exception as e:  # noqa: BLE001
        log.error(f"lienzo: {e!r}")
    if qwin is None and fallback_widget is not None:
        try:
            qwin = fallback_widget.window()
            log.info("lienzo: ventana obtenida del docker")
        except Exception:  # noqa: BLE001
            qwin = None
    if qwin is None:
        log.error("lienzo: sin ventana")
        return None
    best, best_depth = None, -1
    try:
        areas = qwin.findChildren(QtWidgets.QAbstractScrollArea)
    except Exception:  # noqa: BLE001
        return None
    # Descartar áreas pequeñas (dockers, paneles) para no confundirlas con el lienzo.
    min_area = max(1, int(qwin.width() * qwin.height() * 0.10))
    log.info(f"lienzo: {len(areas)} áreas de desplazamiento, ventana {qwin.width()}x{qwin.height()}")
    for area in areas:
        try:
            if not area.isVisible():
                continue
            vp = area.viewport()
            if vp is None or vp.width() * vp.height() < min_area:
                continue
            for child in vp.findChildren(QtWidgets.QWidget):
                if not child.isVisible():
                    continue
                g = child.geometry()
                if g.x() == 0 and g.y() == 0 and g.width() == vp.width() and g.height() == vp.height():
                    depth = _depth(child, qwin)
                    if depth > best_depth:
                        best, best_depth = child, depth
        except Exception:  # noqa: BLE001
            continue
    if best is not None:
        log.info(f"lienzo: {type(best).__name__} {best.width()}x{best.height()}")
        return best
    log.error("lienzo: ningún hijo del viewport coincide; usando reserva")
    # Reserva: el área de desplazamiento más grande con viewport.
    fallback, fallback_area = None, 0
    for w in qwin.findChildren(QtWidgets.QWidget):
        try:
            if not w.isVisible() or not hasattr(w, "viewport"):
                continue
            area_px = w.width() * w.height()
            if area_px > fallback_area:
                fallback, fallback_area = w.viewport(), area_px
        except Exception:  # noqa: BLE001
            continue
    if fallback is not None:
        log.info(f"lienzo (reserva): {type(fallback).__name__} {fallback.width()}x{fallback.height()}")
    else:
        log.error("lienzo: sin candidato de reserva")
    return fallback


def image_transform(view):
    """Transformación imagen -> widget (para dibujar la máscara encima)."""
    try:
        to_canvas, to_image = _transforms(view)
        inv, ok = to_image.inverted()
        if ok:
            # Qt aplica en el orden escrito: imagen -> flake -> widget.
            return inv * to_canvas
    except Exception:  # noqa: BLE001
        pass
    return None


def _depth(widget, root) -> int:
    """Profundidad del widget en el árbol (para quedarse con el más interno)."""
    n = 0
    w = widget
    while w is not None and w is not root:
        n += 1
        w = w.parent() if hasattr(w, "parent") else None
    return n


def _transforms(view):
    """(flake->widget, flake->imagen). Los métodos viven en View, no en Canvas."""
    return view.flakeToCanvasTransform(), view.flakeToImageTransform()


def widget_to_image(view, pos: QPointF, doc_size=None) -> QPointF:
    """De coordenadas del widget del lienzo a píxeles de imagen.

    Si se conoce el tamaño del documento, se prefiere la cadena de
    transformaciones cuyo resultado cae dentro de la imagen.
    """
    try:
        to_canvas, to_image = _transforms(view)
        inv, ok = to_canvas.inverted()
        if not ok:
            log.error("coordenadas: transformación no invertible")
            return pos
        flake = inv.map(pos)
        first = to_image.map(flake)
        if doc_size is None:
            return first
        if 0 <= first.x() < doc_size[0] and 0 <= first.y() < doc_size[1]:
            return first
        alt = view.flakeToDocumentTransform().map(flake)
        if 0 <= alt.x() < doc_size[0] and 0 <= alt.y() < doc_size[1]:
            log.info("coordenadas: usando flake->document")
            return alt
        return first
    except Exception as e:  # noqa: BLE001
        log.error(f"coordenadas: {e!r}")
    return pos


def image_to_widget(view, pos: QPointF) -> QPointF:
    """De píxeles de imagen a coordenadas del widget del lienzo."""
    try:
        to_canvas, to_image = _transforms(view)
        inv, ok = to_image.inverted()
        if ok:
            return to_canvas.map(inv.map(pos))
    except Exception:  # noqa: BLE001
        pass
    return pos


class Capture(QObject):
    """Filtro de aplicación que recoge trazos solo dentro del lienzo."""

    def __init__(self, controller):
        super().__init__()
        self.c = controller
        self.active = False
        self.target = None
        self.space_down = False
        # Con tableta, Qt manda el MISMO gesto dos veces (TabletPress y luego
        # su eco de ratón). Sin esta bandera cada pincelada dejaba un trazo
        # fantasma de 1 punto antes del bueno, y ese punto solo bastaba para
        # que el segmento se quedara a medias (sesión 9).
        self._stroke_open = False

    def start(self) -> bool:
        self.target = find_canvas_widget(self.c.window)
        if self.target is None:
            log.error("captura: sin lienzo")
            return False
        self._prev_tracking = self.target.hasMouseTracking()
        self.target.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)
        self.active = True
        log.info(f"captura activa en {type(self.target).__name__} {self.target.width()}x{self.target.height()}")
        return True

    def stop(self) -> None:
        self.active = False
        self._stroke_open = False
        try:
            if self.target is not None:
                self.target.setMouseTracking(getattr(self, "_prev_tracking", False))
        except Exception:  # noqa: BLE001
            pass
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:  # noqa: BLE001
            pass

    def _inside(self, obj) -> bool:
        w = obj
        while w is not None:
            if w is self.target:
                return True
            w = w.parent() if hasattr(w, "parent") else None
        return False

    def eventFilter(self, obj, ev):  # noqa: N802
        if not self.active or QApplication.activeModalWidget() is not None:
            return False
        t = ev.type()
        if t == event_type("KeyPress"):
            handled = self._handle_key(ev)
            if not handled and ev.key() == key_code("Key_Space"):
                self.space_down = True
            return handled
        if t == event_type("KeyRelease"):
            if ev.key() == key_code("Key_Space"):
                self.space_down = False
            return False
        if t in TABLET_PRESS or t in TABLET_MOVE or t in TABLET_RELEASE:
            return self._handle(ev, obj)
        if t in PRESS or t in MOVE or t in RELEASE:
            return self._handle(ev, obj)
        return False

    def _handle_key(self, ev) -> bool:
        """Ctrl+Z deshace el último paso de la herramienta."""
        try:
            key = ev.key()
            if key in (key_code("Key_Delete"), key_code("Key_Backspace")):
                if getattr(self.c, "selected", None) is not None:
                    self.c.delete_selected()
                    return True
                return False
            mods = ev.modifiers()
            ctrl = keyboard_modifier("ControlModifier")
            if not (mods & ctrl) or key != key_code("Key_Z"):
                return False
            if not self.c.tool_is_neutral():
                return False
        except Exception:  # noqa: BLE001
            return False
        self.c.undo()
        return True

    def _handle(self, ev, obj) -> bool:
        if self.space_down:
            return False
        if not self._inside(obj):
            return False
        pos = event_pos(ev)
        tgt = self.target
        if obj is not tgt:
            gp = obj.mapToGlobal(pos.toPoint())
            pos = QPointF(tgt.mapFromGlobal(gp))
        if not tgt.rect().contains(pos.toPoint()):
            return False
        doc = self.c.document
        size = (doc.width(), doc.height()) if doc is not None else None
        img = widget_to_image(self.c.view, pos, size)
        t = ev.type()
        if t in PRESS or t in TABLET_PRESS:
            if self._stroke_open:
                return False  # eco de tableta/ratón del mismo gesto
            if not self._left_or_tablet(ev, t):
                return False
            if not self.c.tool_is_neutral():
                return False
            self._stroke_open = True
            self.c.set_hover(pos)
            self.c.begin_stroke(img)
            return True
        if t in MOVE or t in TABLET_MOVE:
            if not self.c.tool_is_neutral():
                return False
            self.c.set_hover(pos)
            if self._drawing(ev):
                self.c.add_point(img)
                return True
            return False
        if t in RELEASE or t in TABLET_RELEASE:
            if not self._stroke_open:
                return False  # el final ya lo dio el otro evento del gesto
            self._stroke_open = False
            if not self.c.tool_is_neutral():
                return False
            self.c.end_stroke()
            return True
        return False

    @staticmethod
    def _left_or_tablet(ev, t) -> bool:
        if t in TABLET_PRESS:
            return True
        try:
            return ev.button() == mouse_button("LeftButton")
        except Exception:  # noqa: BLE001
            return True

    @staticmethod
    def _drawing(ev) -> bool:
        try:
            return bool(ev.buttons())
        except Exception:  # noqa: BLE001
            return True
