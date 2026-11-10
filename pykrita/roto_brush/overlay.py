"""Dibuja los trazos, la previsualización de la máscara y el cursor."""

from . import log
from .canvas import image_to_widget, image_transform
from .qt import (
    QPointF,
    QtGui,
    QtWidgets,
    cap_style,
    cursor_shape,
    image_format,
    join_style,
    painter_hint,
    widget_attr,
)

COLORS = {
    0: (0, 200, 90, 220),  # FG verde
    1: (230, 40, 40, 220),  # BG rojo
    2: (60, 140, 255, 220),  # Refine azul
    3: (255, 160, 0, 220),  # Refine erase naranja
}


class Overlay(QtWidgets.QWidget):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.c = controller
        self.hover = None
        self._mask_key = None
        self._mask_img = None
        self.setAttribute(widget_attr("WA_TransparentForMouseEvents"))
        self.setAttribute(widget_attr("WA_NoSystemBackground"))
        self.setAttribute(widget_attr("WA_TranslucentBackground"))
        self.setCursor(cursor_shape("BlankCursor"))
        self.show()
        self.sync()

    def sync(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(0, 0, parent.width(), parent.height())
            self.raise_()
            if not self.isVisible():
                self.show()

    def set_hover(self, pos) -> None:
        self.hover = pos
        self.update()

    def paintEvent(self, _ev):  # noqa: N802
        try:
            self._paint()
        except Exception as e:  # noqa: BLE001
            log.error(f"overlay: {e!r}")

    def _paint(self) -> None:
        view = self.c.view
        if view is None:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(painter_hint("Antialiasing"))
        painter.setRenderHint(painter_hint("SmoothPixmapTransform"))
        try:
            zoom = float(view.canvas().zoomLevel()) or 1.0
        except Exception:  # noqa: BLE001
            zoom = 1.0
        mask = getattr(self.c, "mask", None)
        if mask is not None:
            mode = "gray" if getattr(self.c, "view_mask", False) else "dim"
            self._draw_mask(painter, mode, mask)
        self._draw_strokes(painter)
        if self.hover is not None and not getattr(self.c, "edit_mode", False):
            self._draw_cursor(painter, zoom)
        painter.end()

    def _mask_image(self, mode: str, mask):
        key = (id(mask[0]), mode)
        if key == self._mask_key:
            return self._mask_img
        alpha, rect = mask
        try:
            if mode == "gray":
                data = self.c.engine.gray_mask(alpha, rect[2], rect[3])
            else:
                data = self.c.engine.dim_mask(alpha, rect[2], rect[3])
            self._mask_img = QtGui.QImage(
                data, rect[2], rect[3], image_format("Format_RGBA8888")
            ).copy()
        except Exception as e:  # noqa: BLE001
            log.error(f"overlay mascara: {e!r}")
            self._mask_img = None
        self._mask_key = key
        return self._mask_img

    def _draw_mask(self, painter, mode: str, mask) -> None:
        img = self._mask_image(mode, mask)
        if img is None:
            return
        t = image_transform(self.c.view)
        if t is None:
            return
        rect = mask[1]
        painter.save()
        painter.setTransform(t)
        painter.drawImage(QPointF(rect[0], rect[1]), img)
        painter.restore()

    def _draw_strokes(self, painter) -> None:
        view = self.c.view
        edit = getattr(self.c, "edit_mode", False)
        hidden = 0 if edit else getattr(self.c, "computed_strokes", 0)
        selected = getattr(self.c, "selected", None) if edit else None
        for idx, (kind, _radius, points, _feather) in enumerate(self.c.strokes[hidden:], start=hidden):
            if not points:
                continue
            pts = [image_to_widget(view, QPointF(x, y)) for x, y in points]
            r, g, b, a = COLORS.get(kind, (255, 255, 255, 200))
            if idx == selected:
                halo = QtGui.QPen(QtGui.QColor(255, 255, 255, 240))
                halo.setWidthF(5.0)
                halo.setCapStyle(cap_style("RoundCap"))
                painter.setPen(halo)
                if len(pts) == 1:
                    painter.drawPoint(pts[0])
                else:
                    painter.drawPolyline(pts)
            pen = QtGui.QPen(QtGui.QColor(r, g, b, a))
            pen.setWidthF(3.5 if idx == selected else 2.0)
            pen.setCapStyle(cap_style("RoundCap"))
            pen.setJoinStyle(join_style("RoundJoin"))
            painter.setPen(pen)
            if len(pts) == 1:
                painter.drawPoint(pts[0])
            else:
                painter.drawPolyline(pts)

    def _draw_cursor(self, painter, zoom: float) -> None:
        radius = max(1.0, self.c.brush * zoom)
        center = self.hover
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 220))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(QtGui.QColor(255, 255, 255, 40))
        painter.drawEllipse(center, radius, radius)
        pen.setColor(QtGui.QColor(255, 255, 255, 200))
        painter.setBrush(QtGui.QBrush())
        painter.setPen(pen)
        painter.drawEllipse(center, radius, radius)
