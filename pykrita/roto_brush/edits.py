"""Trazos: alta, selección, edición y pila de deshacer."""

from . import log
from .engine import FG, MODEL, REFINE, REFINE_ERASE


class StrokeEdits:
    def _snapshot(self) -> None:
        self.undo_stack.append(
            [ [k, r, [list(p) for p in pts], f] for k, r, pts, f in self.strokes ]
        )
        if len(self.undo_stack) > 60:
            self.undo_stack.pop(0)

    def undo(self) -> None:
        """Ctrl+Z dentro de la herramienta: deshace el último paso."""
        if self.applied and self.source is not None:
            node_id, rect, orig = self.source
            node = self._source_node
            if node is not None and self._key_of(node) == node_id:
                try:
                    node.setPixelData(orig, rect[0], rect[1], rect[2], rect[3])
                    doc = self.document
                    if doc is not None:
                        doc.refreshProjection()
                    self.applied = False
                    self.status.emit("aplicación deshecha")
                    log.info("undo: aplicación deshecha")
                    return
                except Exception as e:  # noqa: BLE001
                    log.error(f"undo aplicar: {e!r}")
        if not self.undo_stack:
            self.status.emit("nada que deshacer")
            return
        snap = self.undo_stack.pop()
        self.strokes = [ [k, r, [list(p) for p in pts], f] for k, r, pts, f in snap ]
        self.mask = None
        self.computed_strokes = 0
        self.selected = None
        self._refresh()
        self.status.emit("deshecho")

    @staticmethod
    def _dist_to_stroke(p, pts) -> float:
        if not pts:
            return 1e9
        if len(pts) == 1:
            return ((p[0] - pts[0][0]) ** 2 + (p[1] - pts[0][1]) ** 2) ** 0.5
        best = 1e9
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            dx, dy = x1 - x0, y1 - y0
            l2 = dx * dx + dy * dy
            t = 0.0 if l2 < 1e-9 else max(0.0, min(1.0, ((p[0] - x0) * dx + (p[1] - y0) * dy) / l2))
            px, py = x0 + dx * t, y0 + dy * t
            best = min(best, ((p[0] - px) ** 2 + (p[1] - py) ** 2) ** 0.5)
        return best

    def select_at(self, img) -> bool:
        """Selecciona el trazo más cercano al punto (para editarlo)."""
        best, best_d = None, 14.0
        for i, (_k, _r, pts, _f) in enumerate(self.strokes):
            d = self._dist_to_stroke((img.x(), img.y()), pts)
            if d < best_d:
                best, best_d = i, d
        self.selected = best
        self._refresh()
        if best is None:
            self.status.emit("ningún trazo cerca")
        else:
            kind, radius, _pts, feather = self.strokes[best]
            nombre = {0: "verde", 1: "rojo", 2: "refine", 3: "borrar refine"}.get(kind, "?")
            extra = f", feather propio {feather:.1f}" if feather > 0 else ""
            self.status.emit(f"trazo {best + 1} ({nombre}, pincel {radius:.0f}{extra}) seleccionado")
        return best is not None

    def delete_selected(self) -> None:
        if self.selected is None:
            self.status.emit("selecciona un trazo primero")
            return
        self._snapshot()
        try:
            del self.strokes[self.selected]
        except IndexError:
            self.selected = None
            return
        self.selected = None
        self.mask = None
        self.computed_strokes = 0
        self._refresh()
        self.status.emit("trazo borrado")

    def set_selected_kind(self, kind: int) -> None:
        """Cambia el tipo del trazo seleccionado (verde, rojo, refine)."""
        if self.selected is None or self.selected >= len(self.strokes):
            self.status.emit("selecciona un trazo primero")
            return
        self._snapshot()
        self.strokes[self.selected][0] = int(kind)
        self.mask = None
        self.computed_strokes = 0
        self._refresh()
        self.status.emit(f"trazo {self.selected + 1}: tipo cambiado")

    def set_selected_feather(self, value: float) -> None:
        """Feather propio del trazo seleccionado (0 = usar el global)."""
        if self.selected is None or self.selected >= len(self.strokes):
            self.status.emit("selecciona un trazo primero")
            return
        self._snapshot()
        self.strokes[self.selected][3] = float(value) if value > 0.05 else -1.0
        self.mask = None
        self.computed_strokes = 0
        self._refresh()
        txt = f"{value:.1f}" if value > 0.05 else "heredado"
        self.status.emit(f"trazo {self.selected + 1}: feather {txt}")

    def set_brush(self, value: float) -> None:
        self.brush = float(value)
        if self.edit_mode and self.selected is not None and self.selected < len(self.strokes):
            self.strokes[self.selected][1] = float(value)
            self.mask = None
            self._refresh()
            self.status.emit(f"trazo {self.selected + 1}: pincel {value:.0f}")

    def begin_stroke(self, img) -> None:
        self._sync_document()
        if self.edit_mode:
            self.select_at(img)
            return
        self.computed_strokes = 0
        doc = self.document
        if doc is not None and not (0 <= img.x() < doc.width() and 0 <= img.y() < doc.height()):
            log.error(f"trazo fuera de la imagen: ({img.x():.1f}, {img.y():.1f}) doc={doc.width()}x{doc.height()}")
            self.status.emit("ese clic cae fuera del lienzo")
            self._bad_points += 1
            return
        if not self.strokes:
            log.info(f"primer trazo en imagen: ({img.x():.1f}, {img.y():.1f})")
        self._snapshot()
        radius = float(self.brush) if self.mode in (REFINE, REFINE_ERASE) else 8.0
        self.strokes.append([self.mode, radius, [[img.x(), img.y()]], -1.0])
        self._refresh()

    def add_point(self, img) -> None:
        if self.edit_mode:
            return
        if not self.strokes:
            return
        pts = self.strokes[-1][2]
        x, y = img.x(), img.y()
        if pts and abs(pts[-1][0] - x) < 1.5 and abs(pts[-1][1] - y) < 1.5:
            return
        pts.append([x, y])
        self._refresh()

    def end_stroke(self) -> None:
        if not self.strokes:
            return
        kind, _r, pts, _f = self.strokes[-1]
        log.info(f"trazo {kind} con {len(pts)} puntos")
        if self.auto_preview:
            self.status.emit(f"{len(self.strokes)} trazos, calculando…")
            self._timer.start()
        else:
            self.status.emit(f"{len(self.strokes)} trazos (pulsa Recalcular)")

    def clear(self) -> None:
        self._timer.stop()
        self._snapshot()
        self.strokes = []
        self.mask = None
        self.source = None
        self.computed_strokes = 0
        self.selected = None
        self._refresh()
        self.status.emit("trazos borrados")

    # -- cálculo --------------------------------------------------------------

    def _strokes_inside(self, rect) -> bool:
        """¿Cae algún punto dentro del área de la capa?"""
        x0, y0, w, h = rect
        for _kind, _radius, pts, _feather in self.strokes:
            for x, y in pts:
                if x0 <= x < x0 + w and y0 <= y < y0 + h:
                    return True
        return False
