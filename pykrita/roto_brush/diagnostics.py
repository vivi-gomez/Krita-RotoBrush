"""Pruebas automáticas y volcado de diagnóstico (solo con variables de entorno)."""

import os

from . import canvas, log
from .canvas import widget_to_image
from .engine import MODEL, Params
from .qt import QEvent, Qt, QtCore, QtGui, QtWidgets


def fmt(t) -> str:
    try:
        return f"m11={t.m11():.3f} m12={t.m12():.3f} m21={t.m21():.3f} m22={t.m22():.3f} dx={t.dx():.1f} dy={t.dy():.1f}"
    except Exception:  # noqa: BLE001
        return str(t)


def _mouse_event(kind: str, local, glob):
    """QMouseEvent compatible con Qt5 y Qt6."""
    t = getattr(QEvent.Type, kind) if hasattr(QEvent, "Type") else getattr(QEvent, kind)
    left = Qt.MouseButton.LeftButton if hasattr(Qt, "MouseButton") else Qt.LeftButton
    try:
        return QtGui.QMouseEvent(t, local, glob, left, left, Qt.KeyboardModifier.NoModifier)
    except TypeError:
        return QtGui.QMouseEvent(t, local, glob, left, left, Qt.KeyboardModifier.NoModifier, Qt.MouseEventSource.MouseEventNotSynthesized)



class Diagnostics:
    def dump_ui(self) -> None:
        """Diagnóstico: widgets del lienzo y transformaciones."""
        try:
            w = self.window
            view = self.view
            if w is None or view is None:
                log.info("dump: sin ventana o vista")
                return
            zoom = None
            try:
                zoom = view.canvas().zoomLevel()
            except Exception:  # noqa: BLE001
                pass
            doc = view.document()
            size = f"{doc.width()}x{doc.height()}" if doc is not None else "?"
            log.info(f"dump: view={type(view).__name__} doc={size} zoom={zoom}")
            log.info(f"dump: flake->canvas {fmt(view.flakeToCanvasTransform())}")
            log.info(f"dump: flake->imagen {fmt(view.flakeToImageTransform())}")
            t = canvas.image_transform(view)
            if t is not None:
                a = t.map(QtCore.QPointF(0, 0))
                b = t.map(QtCore.QPointF(512, 512))
                log.info(f"dump: imagen(0,0)->({a.x():.1f},{a.y():.1f}) imagen(512,512)->({b.x():.1f},{b.y():.1f})")
            cw = canvas.find_canvas_widget(w)
            if cw is not None:
                g = cw.mapToGlobal(QtCore.QPoint(0, 0))
                c = cw.rect().center()
                img = widget_to_image(view, QtCore.QPointF(c))
                log.info(
                    f"dump: elegido {type(cw).__name__} {cw.width()}x{cw.height()} "
                    f"global=({g.x()},{g.y()}) centro->imagen({img.x():.1f},{img.y():.1f})"
                )
            qwin = w.qwindow()
            cands = []
            for widget in qwin.findChildren(QtWidgets.QWidget):
                if not widget.isVisible():
                    continue
                area = widget.width() * widget.height()
                if hasattr(widget, "viewport") or area > 50000:
                    cands.append((area, widget))
            cands.sort(key=lambda t: t[0], reverse=True)
            for _area, widget in cands[:10]:
                g = widget.mapToGlobal(QtCore.QPoint(0, 0))
                vp = widget.viewport() if hasattr(widget, "viewport") else None
                log.info(
                    f"dump: {type(widget).__name__} name={widget.objectName()} "
                    f"{widget.width()}x{widget.height()} global=({g.x()},{g.y()}) "
                    f"viewport={vp is not None}"
                )
                for label, box in [("propio", widget)] + ([("viewport", vp)] if vp is not None else []):
                    c = box.rect().center()
                    img = widget_to_image(view, QtCore.QPointF(c))
                    log.info(f"dump:   {label} centro({c.x()},{c.y()}) -> imagen({img.x():.1f},{img.y():.1f})")
        except Exception as e:  # noqa: BLE001
            log.error(f"dump: {e!r}")

    # -- contexto -------------------------------------------------------------

    def selftest(self) -> None:
        """Autoprueba: trazos fijos en coordenadas de imagen -> PNG con alfa."""
        out = os.environ.get("ROTO_BRUSH_SELFTEST", "")
        try:
            doc = self.document
            node = doc.activeNode() if doc is not None else None
            if node is None:
                log.error("selftest: sin capa")
                return
            w, h = doc.width(), doc.height()
            strokes = [
                [0, 24.0, [[512, 330], [512, 430]], -1.0],
                [0, 24.0, [[300, 620], [740, 640]], -1.0],
                [0, 24.0, [[512, 760], [300, 880]], -1.0],
                [1, 24.0, [[40, 40]], -1.0],
                [1, 24.0, [[980, 40]], -1.0],
                [1, 24.0, [[40, 980]], -1.0],
                [1, 24.0, [[980, 980]], -1.0],
            ]
            bounds = node.bounds()
            rect = (bounds.x(), bounds.y(), bounds.width(), bounds.height())
            px = bytes(node.pixelData(*rect))
            log.info(f"selftest: primer píxel {list(px[:4])}")
            params = Params(
                engine=MODEL, best=1, feather=1.0, smooth=1.0, shift=0.0,
                contrast=0.0, decontaminate=1, bgra=1, sam_weight=6.0,
                search_radius=15.0, clean=1, fill_holes=1,
            )
            if not self.engine.has_model:
                self.engine.load_model(self.model_path)
            alpha = self.engine.render(px, rect[2], rect[3], strokes, params)
            buf = bytearray(px)
            for i in range(rect[2] * rect[3]):
                buf[i * 4 + 3] = (buf[i * 4 + 3] * alpha[i]) // 255
                buf[i * 4], buf[i * 4 + 2] = buf[i * 4 + 2], buf[i * 4]
            img = QtGui.QImage(bytes(buf), rect[2], rect[3], QtGui.QImage.Format.Format_RGBA8888)
            log.info(f"selftest: guardado {out} ({w}x{h}, capa {rect[2]}x{rect[3]})")
            img.copy().save(out, "PNG")
            fg = sum(1 for a in alpha if a > 127)
            log.info(f"selftest: primer plano {fg * 100.0 / len(alpha):.1f} %")
        except Exception as e:  # noqa: BLE001
            log.error(f"selftest: {e!r}")

    def event_test(self) -> None:
        """Simula un clic en el centro del lienzo y registra el punto resultante."""
        try:
            self._sync_document()
            if not self.set_capture(True):
                log.error("eventtest: sin captura")
                return
            target = self.capture.target
            try:
                cv = self.view.canvas()
                if os.environ.get("ROTO_BRUSH_ZOOM"):
                    cv.setZoomLevel(float(os.environ["ROTO_BRUSH_ZOOM"]))
                    cv.pan(QtCore.QPoint(300, 200))
                    log.info(f"eventtest: zoom={cv.zoomLevel()} con desplazamiento")
            except Exception as e:  # noqa: BLE001
                log.error(f"eventtest zoom: {e!r}")
            c = target.rect().center()
            local = QtCore.QPointF(c)
            glob = QtCore.QPointF(target.mapToGlobal(c))
            ev = _mouse_event("MouseButtonPress", local, glob)
            QtWidgets.QApplication.sendEvent(target, ev)
            ev2 = _mouse_event("MouseButtonRelease", local, glob)
            QtWidgets.QApplication.sendEvent(target, ev2)
            log.info(f"eventtest: centro widget ({c.x()},{c.y()}) trazos={len(self.strokes)}")
            if self.strokes:
                log.info(f"eventtest: punto imagen {self.strokes[0][2][0]}")
            self.compute()
            loop = QtCore.QEventLoop()
            self.done.connect(lambda _p: loop.quit())
            QtCore.QTimer.singleShot(15000, loop.quit)
            loop.exec()
            log.info(f"eventtest: mascara={self.mask is not None} aplicada={self.applied}")
            self.apply()
            log.info(f"eventtest: aplicada={self.applied}")
            self.set_capture(False)
        except Exception as e:  # noqa: BLE001
            log.error(f"eventtest: {e!r}")
