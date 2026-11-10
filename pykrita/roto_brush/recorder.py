"""Registro de trazos e imagen original para reproducirlos fuera de Krita.

Se activa con el archivo ~/.local/share/krita/roto_brush_record o con la
variable de entorno ROTO_BRUSH_RECORD. Cada sesión de captura (activar la
herramienta -> desactivar/cerrar) crea una carpeta nueva en
<proyecto>/tests/recordings/sesion-AAAAMMDD-HHMMSS/ con:

  meta.json      documento, rectángulo de la capa, parámetros, eventos
  strokes.jsonl  una línea por trazo terminado y por máscara calculada
  layer.bgra     píxeles crudos de la capa (w*h*4, BGRA) en el rect de meta

Con eso el arnés tests/replay_recording.py puede repetir los trazos exactos
del usuario contra SAM 2.1 y compararlos con la referencia de EffectCraft.
"""

import json
import os
import time
from pathlib import Path

from . import log

_MARK = Path.home() / ".local" / "share" / "krita" / "roto_brush_record"


def enabled() -> bool:
    return bool(os.environ.get("ROTO_BRUSH_RECORD")) or _MARK.exists()


class Recorder:
    """Escapa cualquier error: registrar jamás puede romper la herramienta."""

    def __init__(self):
        self.dir = None
        self.meta = {}
        self._img_saved = False

    # -- infraestructura ------------------------------------------------

    def _root(self) -> Path:
        try:
            from . import engine_runner

            d = engine_runner.engine_dir()
            if d is not None:
                return Path(d) / "tests" / "recordings"
        except Exception:  # noqa: BLE001
            pass
        return Path.home() / ".local" / "share" / "krita" / "roto_brush" / "recordings"

    def _event(self, obj: dict) -> None:
        if self.dir is None:
            return
        try:
            obj = {"ts": time.strftime("%H:%M:%S"), **obj}
            with (self.dir / "strokes.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj) + "\n")
        except Exception as e:  # noqa: BLE001
            log.error(f"recorder evento: {e!r}")

    def _write_meta(self) -> None:
        if self.dir is None:
            return
        try:
            (self.dir / "meta.json").write_text(
                json.dumps(self.meta, indent=1, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:  # noqa: BLE001
            log.error(f"recorder meta: {e!r}")

    # -- puntos de enganche ----------------------------------------------

    def begin(self, c) -> None:
        """Al activar la captura: sesión nueva (la anterior queda cerrada)."""
        self.dir = None
        self._img_saved = False
        if not enabled():
            return
        try:
            root = self._root()
            root.mkdir(parents=True, exist_ok=True)
            name = os.environ.get("ROTO_BRUSH_RECORD_SESSION") or time.strftime(
                "sesion-%Y%m%d-%H%M%S"
            )
            d = root / name
            d.mkdir(exist_ok=True)
            self.dir = d
            self.meta = {"ts": time.strftime("%Y-%m-%d %H:%M:%S")}
            try:
                self.meta.update(self._doc_info(c.document))
            except Exception as e:  # noqa: BLE001
                log.error(f"recorder doc: {e!r}")
            self.meta["engine_kind"] = getattr(c, "engine_kind", "sam2")
            self.meta["edge_smooth"] = c.edge_smooth
            self.meta["brush"] = c.brush
            self._write_meta()
            log.info(f"recorder: sesión en {d}")
        except Exception as e:  # noqa: BLE001
            log.error(f"recorder begin: {e!r}")
            self.dir = None

    @staticmethod
    def _doc_info(doc) -> dict:
        """Todo lo que la API de Krita permita preguntar por el documento."""
        info = {}
        if doc is None:
            return info
        for key, names in (
            ("document", ("name",)),
            ("url", ("filePath", "filepath", "fileName")),
        ):
            for attr in names:
                try:
                    value = getattr(doc, attr)()
                except Exception:  # noqa: BLE001
                    continue
                if value:
                    info[key] = value
                    break
        for key, attr in (("width", "width"), ("height", "height")):
            try:
                info[key] = getattr(doc, attr)()
            except Exception:  # noqa: BLE001
                pass
        return info

    def layer_info(self, c) -> None:
        """Datos de la capa activa (nombre, id, rec) en meta."""
        if self.dir is None:
            return
        try:
            node = c.document.activeNode()
            if node is None:
                return
            b = node.bounds()
            self.meta["layer"] = node.name()
            self.meta["layer_kind"] = node.type()
            self.meta["layer_bounds"] = [b.x(), b.y(), b.width(), b.height()]
            self._write_meta()
        except Exception:  # noqa: BLE001
            pass

    def image(self, c) -> None:
        """Vuelca los píxeles originales de la capa una sola vez por sesión."""
        if self.dir is None or self._img_saved:
            return
        try:
            if c.source is None:
                return
            _node_id, rect, px = c.source
            (self.dir / "layer.bgra").write_bytes(px)
            self.meta["rect"] = list(rect)
            self.meta["image"] = {"w": rect[2], "h": rect[3], "bytes": len(px)}
            self._img_saved = True
            self._write_meta()
            self._event({"ev": "image", "rect": list(rect)})
        except Exception as e:  # noqa: BLE001
            log.error(f"recorder imagen: {e!r}")

    def stroke(self, c) -> None:
        """Un trazo recién terminado: se guarda la lista COMPLETA de trazos."""
        if self.dir is None:
            return
        try:
            self.image(c)
            self._event(
                {
                    "ev": "strokes",
                    "n": len(c.strokes),
                    "strokes": [
                        [int(k), float(r), [[round(p[0], 2), round(p[1], 2)] for p in pts], float(f)]
                        for k, r, pts, f in c.strokes
                    ],
                }
            )
        except Exception as e:  # noqa: BLE001
            log.error(f"recorder trazo: {e!r}")

    def mask(self, c, pct: float, engine: str) -> None:
        if self.dir is None:
            return
        try:
            self._event(
                {"ev": "mask", "pct": round(float(pct), 2),
                 "strokes": len(c.strokes), "engine": engine}
            )
        except Exception:  # noqa: BLE001
            pass

    def note(self, text: str) -> None:
        if self.dir is None:
            return
        self._event({"ev": "note", "text": text})
