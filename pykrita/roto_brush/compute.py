"""Cálculo en hilo aparte, vista previa, aplicar y restaurar."""

import os
import threading
import time

from krita import Krita

from . import canvas, log
from . import sam2_client
from .maskops import _dilate1, _erase_component, _merge
from .engine import FG, MODEL, Engine, Params, BG, REFINE, REFINE_ERASE
from .qt import QtCore, QtGui, QtWidgets, pyqtSignal


class ComputeOps:
    def changed(self) -> None:
        """Un ajuste cambió: si hay máscara, recalcúlala."""
        if self.mask is not None and self.auto_preview:
            self._timer.start()

    def reset_params(self) -> None:
        """Vuelve a los valores de fábrica."""
        self.mode = FG
        self.brush = 18.0
        self.feather = 1.5
        self.smooth = 1.0
        self.contrast = 0.0
        self.shift = 0.0
        self.search_radius = 15.0
        self.sam_weight = 6.0
        self.clean = True
        self.fill_holes = True
        self.decontaminate = True
        self.best = True
        self.auto_preview = True
        self.edge_smooth = 8
        self.engine_kind = "sam2"
        self.edit_mode = False
        self.view_mask = False
        self.selected = None
        self.params_reset.emit()
        self.status.emit("ajustes restablecidos")

    def compute(self) -> None:
        if not self.strokes:
            self.status.emit("pinta primero sobre el personaje")
            return
        if self.busy:
            self.pending = True
            return
        doc = self._sync_document()
        if not any(s[2] for s in self.strokes):
            self.status.emit("pinta primero sobre el personaje (verde)")
            return
        if not any(s[0] == FG and s[2] for s in self.strokes):
            self.status.emit("necesito al menos un trazo verde de primer plano")
            return
        node = doc.activeNode() if doc is not None else None
        if node is None:
            self.status.emit("no hay capa activa")
            return
        if node.type() != "paintlayer":
            self.status.emit("la capa activa no es de pintura")
            return
        depth, model_cs = node.colorDepth(), node.colorModel()
        if depth != "U8" or model_cs != "RGBA":
            self.status.emit(f"capa no soportada: {model_cs} {depth} (usa RGBA de 8 bits)")
            return
        bounds = node.bounds()
        if bounds.isEmpty():
            self.status.emit("la capa está vacía")
            return
        node_id = self._key_of(node)
        if self.source is None or self.source[0] != node_id:
            # El área se fija una vez: tras aplicar, node.bounds() se encoge y
            # recalcular con ella desalinearía la máscara.
            rect = (bounds.x(), bounds.y(), bounds.width(), bounds.height())
            px = bytes(node.pixelData(*rect))
            self.source = (node_id, rect, px)
            self._source_node = node
            log.info(f"origen capturado: {rect[2]}x{rect[3]}")
            self.recorder.layer_info(self)
            self.recorder.image(self)
        rect = self.source[1]
        if not self._strokes_inside(rect):
            first = next((s[2][0] for s in self.strokes if s[2]), (0.0, 0.0))
            x, y = first
            self.status.emit(
                f"trazos fuera de la imagen: primer punto ({x:.0f}, {y:.0f}) "
                f"para una capa de {rect[2]}x{rect[3]}"
            )
            log.error(f"trazos fuera del área de la capa rect={rect} muestra={self.strokes[0][2][:2]}")
            return
        px = self.source[2]
        strokes = self._to_layer(self.strokes, rect)
        prior = None
        if self.mask is not None and self.mask[1] == rect:
            prior = bytes(self.mask[0])
        params = Params(
            engine=MODEL,
            best=int(self.best),
            feather=float(self.feather),
            smooth=float(self.smooth),
            shift=float(self.shift),
            contrast=float(self.contrast),
            decontaminate=int(self.decontaminate),
            bgra=1,
            sam_weight=float(self.sam_weight),
            search_radius=float(self.search_radius),
            clean=int(self.clean),
            fill_holes=int(self.fill_holes),
            prior=prior,
            prior_len=len(prior) if prior else 0,
            prior_weight=2.0,
            edge_smooth=int(self.edge_smooth),
        )
        self.busy = True
        self.status.emit("calculando…")
        if getattr(self, "engine_kind", "mobile") == "sam2" and sam2_client.ping():
            threading.Thread(target=self._work_sam2, args=(px, rect, strokes, node), daemon=True).start()
        else:
            if getattr(self, "engine_kind", "mobile") == "sam2":
                self.status.emit("SAM 2.1 no responde: uso MobileSAM")
            threading.Thread(target=self._work, args=(px, rect, strokes, params, node), daemon=True).start()

    @staticmethod
    def _to_layer(strokes, rect):
        """Los trazos están en coordenadas de imagen; el motor trabaja en el
        rectángulo de la capa, que puede estar desplazado."""
        x0, y0 = rect[0], rect[1]
        return [
            (int(k), float(r), [[p[0] - x0, p[1] - y0] for p in pts], float(f))
            for k, r, pts, f in strokes
        ]

    @staticmethod
    def _sam2_prompt(strokes, rect):
        """Puntos para SAM 2.1 (sin caja: el worker elige el mayor candidato)."""
        pts = []
        for kind, _r, points, _f in strokes:
            if kind not in (0, 1):
                continue
            label = 1 if kind == 0 else 0
            n = len(points)
            step = max(1, n // 12)
            chosen = points[::step]
            if chosen[-1] != points[-1]:
                chosen.append(points[-1])
            for pair in chosen:
                pts.append([round(pair[0], 1), round(pair[1], 1), label])
        return pts, None

    @staticmethod
    def _sample(points, label, cap: int = 12):
        """Muestrea ~`cap` puntos de un trazo y los marca con `label`."""
        step = max(1, len(points) // cap)
        chosen = points[::step]
        if chosen[-1] != points[-1]:
            chosen.append(points[-1])
        return [[round(p[0], 1), round(p[1], 1), label] for p in chosen]

    def _work_sam2(self, px, rect, strokes, node):
        """Acumula de verdad: cada trazo verde UNE su máscara al resultado y
        cada rojo resta SOLO su zona barrida. El alfa del worker llega en
        0 o 255, así que unir e intersecar son un OR y un AND de bits."""
        t0 = time.time()
        try:
            acc = None
            green_pts = []
            calls = 0
            w, h = rect[2], rect[3]
            for kind, radius, pts, _f in strokes:
                if not pts:
                    continue
                if kind in (FG, REFINE):
                    # Contexto completo: TODOS los puntos verdes hasta el trazo
                    # actual; si algún cálculo colapsa, la unión no lo pierde.
                    green_pts.extend(self._sample(pts, 1))
                    mask = sam2_client.segment(px, w, h, list(green_pts))
                    calls += 1
                    acc = mask if acc is None else _merge(acc, mask, True)
                elif kind in (BG, REFINE_ERASE):
                    # SAM no sabe "quitar una zona": con puntos negativos
                    # devuelve solo un fragmento. La goma funciona como el
                    # cubo: se va la componente conexa ENTERA que toca el
                    # barrido del trazo, no una banda fija de 32 px.
                    if acc is None:
                        continue
                    acc = _erase_component(acc, pts, radius, w, h)
            if acc is None:
                raise RuntimeError("hace falta al menos un trazo verde")
            fg = sum(1 for a in acc if a > 127) * 100.0 / len(acc)
            log.info(
                f"SAM 2.1 acumulado: {w}x{h} en {time.time() - t0:.2f} s, "
                f"{calls} llamadas, {len(strokes)} trazos, primer plano {fg:.1f} %"
            )
            alpha = acc
            # "Suavizar borde" también manda en SAM 2.1 (0-16 -> 0..2 px).
            blur = min(2.0, max(0.0, float(self.edge_smooth) / 8.0))
            alpha = self.engine.postprocess(
                alpha, w, h, fill=bool(self.fill_holes),
                clean=bool(self.clean), blur=blur,
            )
            alpha = _dilate1(alpha, w)
            fg = sum(1 for a in alpha if a > 127) * 100.0 / len(alpha)
            log.info(f"SAM 2.1 posprocesado: primer plano {fg:.1f} %")
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"SAM 2.1: {e}")
            return
        self.done.emit((alpha, px, rect, node))

    def _work(self, px, rect, strokes, params, node):
        t0 = time.time()
        try:
            if not self.engine.has_model and self.model_path.exists():
                if not self.engine.load_model(self.model_path):
                    raise RuntimeError(f"no se pudo cargar el modelo: {self.model_path}")
            if not self.engine.has_model:
                raise RuntimeError(f"falta el modelo: {self.model_path}")
            alpha = self.engine.render(px, rect[2], rect[3], strokes, params)
            log.info(f"motor: {rect[2]}x{rect[3]} en {time.time() - t0:.2f} s")
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
            return
        self.done.emit((alpha, px, rect, node))

    def _preview(self, payload) -> None:
        """Guarda la máscara y la pinta como vista previa (no toca la capa)."""
        alpha, _orig, rect, _node = payload
        self.mask = (alpha, rect)
        self.computed_strokes = len(self.strokes)
        fg = sum(1 for a in alpha if a > 127)
        pct = fg * 100.0 / max(1, len(alpha))
        log.info(f"mascara: {rect[2]}x{rect[3]}, primer plano {pct:.1f} %")
        self.recorder.mask(self, pct, getattr(self, "engine_kind", "mobile"))
        self.overlay_update()
        self.status.emit(f"máscara {pct:.0f} % · pinta más o pulsa Aplicar")
        self.busy = False
        if self.pending:
            self.pending = False
            self._timer.start()

    def apply(self) -> None:
        """Escribe la transparencia en la capa activa (una sola operación)."""
        if self.mask is None or self.source is None:
            self.status.emit("calcula primero la máscara")
            return
        alpha, mrect = self.mask
        node_id, rect, orig = self.source
        if mrect != rect:
            self.status.emit("la máscara no coincide con la capa: recalcula")
            return
        node = self._source_node
        if node is None or self._key_of(node) != node_id:
            self.status.emit("la capa cambió: no puedo aplicar")
            return
        x, y, w, h = rect
        out = bytearray(orig)
        for i in range(w * h):
            a = out[i * 4 + 3]
            if a:
                out[i * 4 + 3] = (a * alpha[i]) // 255
        self._snapshot()
        try:
            node.setPixelData(bytes(out), x, y, w, h)
            doc = self.document
            if doc is not None:
                doc.refreshProjection()
            self.applied = True
            self.strokes = []
            self.mask = None
            self.computed_strokes = 0
            self.selected = None
            self._refresh()
            fg = sum(1 for i in range(w * h) if out[i * 4 + 3] > 127)
            log.info(f"aplicado: primer plano {fg * 100.0 / (w * h):.1f} %")
            self.status.emit("aplicado en la capa · Restaurar lo deshace")
        except Exception as e:  # noqa: BLE001
            self.status.emit(f"no se pudo aplicar: {e!r}")
            log.error(f"aplicar: {e!r}")

    def restore(self) -> None:
        """Devuelve la capa a su estado original y reinicia los trazos."""
        if self.source is not None:
            node_id, rect, orig = self.source
            node = self._source_node
            if node is not None and self._key_of(node) == node_id:
                try:
                    node.setPixelData(orig, rect[0], rect[1], rect[2], rect[3])
                    doc = self.document
                    if doc is not None:
                        doc.refreshProjection()
                    log.info("capa restaurada")
                except Exception as e:  # noqa: BLE001
                    self.status.emit(f"no se pudo restaurar: {e!r}")
                    return
        self.strokes = []
        self.mask = None
        self.source = None
        self._source_node = None
        self.applied = False
        self.computed_strokes = 0
        self._refresh()
        self.status.emit("restaurado: capa y trazos limpios")


    def _sync_document(self):
        """Si cambia el documento (por identidad estable), se limpian los trazos."""
        doc = self.document
        key = None
        try:
            key = self._key_of(doc.rootNode()) if doc is not None else None
        except Exception:  # noqa: BLE001
            key = None
        if key != self._doc_key:
            self._doc_key = key
            self.strokes = []
            self.source = None
            self._refresh()
            log.info("documento cambiado: trazos borrados")
        return doc

    def _watch_document(self) -> None:
        """Detecta cambios de documento aunque el usuario no toque el pincel."""
        try:
            before = self._doc_key
            self._sync_document()
            if before != self._doc_key:
                if self.capture.active:
                    self.capture.stop()
                    self._drop_overlay()
                    if self.capture.start():
                        self._neutral_tool()
                        self._make_overlay()
                    else:
                        self.armed.emit(False)
                self.status.emit("documento nuevo: trazos limpios")
                self.armed.emit(self.capture.active)
        except Exception as e:  # noqa: BLE001
            log.error(f"watch: {e!r}")

    def _connect_notifier(self) -> None:
        """Krita avisa al abrir/cerrar imágenes: se limpia la herramienta."""
        try:
            n = Krita.instance().notifier()
            for name in ("imageCreated", "imageClosed", "viewCreated", "viewClosed", "windowCreated"):
                sig = getattr(n, name, None)
                if sig is not None:
                    sig.connect(self._on_image_event)
            log.info("notifier conectado")
        except Exception as e:  # noqa: BLE001
            log.error(f"notifier: {e!r}")

    def _on_image_event(self, *_args) -> None:
        log.info("imagen creada/cerrada: limpiando trazos y desactivando")
        self.recorder.note("imagen creada/cerrada")
        self.strokes = []
        self.mask = None
        self.selected = None
        self.computed_strokes = 0
        self._doc_key = None
        self._timer.stop()
        self.capture.stop()
        self._drop_overlay()
        QtCore.QTimer.singleShot(0, self._restore_tool)
        self._remove_undo_shortcut()
        self.reset_params()
        self.armed.emit(False)

    def _rearm(self) -> None:
        if not self.capture.active:
            return
        self.capture.stop()
        self._drop_overlay()
        if self.capture.start():
            self._neutral_tool()
            self._make_overlay()
        else:
            self.armed.emit(False)

    @staticmethod
    def _key_of(node) -> str:
        """Identidad estable de un nodo (Krita crea envoltorios nuevos cada vez)."""
        try:
            return str(node.uniqueId())
        except Exception:  # noqa: BLE001
            return str(id(node))
