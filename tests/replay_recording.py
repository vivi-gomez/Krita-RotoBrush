#!/usr/bin/env python3
"""Reproduce trazos grabados por el plugin y los compara con la referencia.

Usa la grabación de tests/recordings/<sesion>/ (meta.json + strokes.jsonl +
layer.bgra), envía los puntos a SAM 2.1 exactamente igual que el plugin y,
para cada prefijo de trazos (1, 1+2, 1+2+3…), guarda la máscara y mide el
parecido (IoU) con el canal alfa de la imagen de EffectCraft.

Ejecutar con el Python del motor:
    .engine/venv/bin/python tests/replay_recording.py [carpeta_sesion]
Si no se indica carpeta, se usa la última grabación.
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REC_DIR = ROOT / "tests" / "recordings"
DEFAULT_REF = ROOT / "assets" / "Krea2_turbo_style_reference_00001_EFFECTCRAFT.png"

# sam2_client es un módulo suelto sin dependencias de Krita: se carga directo.
_spec = importlib.util.spec_from_file_location(
    "sam2_client", ROOT / "pykrita" / "roto_brush" / "sam2_client.py"
)
sam2_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sam2_client)

# maskops: mismas operaciones de máscara que usa el plugin.
_spec2 = importlib.util.spec_from_file_location(
    "maskops", ROOT / "pykrita" / "roto_brush" / "maskops.py"
)
maskops = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(maskops)
sys.modules["maskops"] = maskops  # para que accumulate lo encuentre

# accumulate: EL criterio de acumulación del plugin (verde UNE, refine
# recortado a su vecindario, rojo quita la componente conexa). El arnés no
# reimplementa nada: si esto pasa y en Krita falla, el fallo es de Krita.
sys.path.insert(0, str(ROOT / "pykrita" / "roto_brush"))
_spec3 = importlib.util.spec_from_file_location(
    "accumulate", ROOT / "pykrita" / "roto_brush" / "accumulate.py"
)
accumulate = importlib.util.module_from_spec(_spec3)
_spec3.loader.exec_module(accumulate)


def latest_session():
    candidates = sorted(
        (d for d in REC_DIR.glob("sesion-*") if (d / "strokes.jsonl").exists()),
        key=lambda d: d.name,
    )
    return candidates[-1] if candidates else None


def load_session(folder: Path):
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    strokes_event = None
    events = []
    for line in (folder / "strokes.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        events.append(ev)
        if ev.get("ev") == "strokes":
            strokes_event = ev
    if strokes_event is None:
        raise SystemExit(f"{folder}: no hay trazos grabados")
    if "layer.bgra" not in {p.name for p in folder.iterdir()}:
        raise SystemExit(f"{folder}: falta layer.bgra (¿se calculó alguna máscara?)")
    return meta, strokes_event["strokes"], events


def to_layer(strokes, rect):
    """Igual que ComputeOps._to_layer: imagen -> rectángulo de la capa."""
    x0, y0 = rect[0], rect[1]
    return [
        (int(k), float(r), [[p[0] - x0, p[1] - y0] for p in pts], float(f))
        for k, r, pts, f in strokes
    ]


def sam2_prompt(strokes):
    """Modo antiguo (heredado): todos los puntos juntos en una sola llamada."""
    pts = []
    for kind, _r, points, _f in strokes:
        if kind not in (0, 1) or not points:
            continue
        label = 1 if kind == 0 else 0
        n = len(points)
        step = max(1, n // 12)
        chosen = points[::step]
        if chosen[-1] != points[-1]:
            chosen.append(points[-1])
        for pair in chosen:
            pts.append([round(pair[0], 1), round(pair[1], 1), label])
    return pts


def sample(points, label, cap: int = 12):
    """Igual que ComputeOps._sample."""
    step = max(1, len(points) // cap)
    chosen = points[::step]
    if chosen[-1] != points[-1]:
        chosen.append(points[-1])
    return [[round(p[0], 1), round(p[1], 1), label] for p in chosen]


def reference_alpha(ref_path: Path, w: int, h: int) -> np.ndarray:
    img = Image.open(ref_path).convert("RGBA")
    if img.size != (w, h):
        img = img.resize((w, h), Image.NEAREST)
    a = np.array(img)[:, :, 3]
    return a > 127


def ensure_worker(timeout_s: float = 180.0) -> None:
    import subprocess
    import time

    if sam2_client.ping():
        return
    print("El worker SAM 2.1 no responde: lo arranco…")
    log = ROOT / ".engine" / "worker.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as out:
        subprocess.Popen(
            [str(ROOT / ".engine" / "venv" / "bin" / "python"),
             str(ROOT / "engine" / "worker.py"), "--port", "8765"],
            cwd=str(ROOT), stdout=out, stderr=out, start_new_session=True,
        )
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(2.0)
        if sam2_client.ping():
            print(f"worker listo en {time.time() - t0:.0f} s")
            return
    raise SystemExit("el worker no llegó a responder; mira .engine/worker.log")


def main() -> int:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_session()
    if folder is None or not folder.is_dir():
        raise SystemExit("no hay grabación; activa la herramienta y pinta un trazo en Krita")
    meta, strokes, _events = load_session(folder)
    rect = meta.get("rect")
    if not rect:
        if "width" not in meta or "height" not in meta:
            raise SystemExit("la grabación no tiene rect ni tamaño de documento")
        rect = [0, 0, meta["width"], meta["height"]]
    w, h = int(rect[2]), int(rect[3])
    raw = (folder / "layer.bgra").read_bytes()
    if len(raw) != w * h * 4:
        raise SystemExit(f"layer.bgra inesperado: {len(raw)} != {w * h * 4}")
    print(f"sesión: {folder.name}  doc={meta.get('document')}  capa={meta.get('layer')} "
          f"rect={rect}  trazos={len(strokes)}")

    ref_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_REF
    ref = reference_alpha(ref_path, w, h) if ref_path.exists() else None
    if ref is None:
        print(f"AVISO: sin referencia en {ref_path}")

    ensure_worker()

    out = folder / "replay"
    out.mkdir(exist_ok=True)
    img = Image.frombytes("RGBA", (w, h), raw)
    b, g, r, a = img.split()
    rgb = Image.merge("RGB", (r, g, b))

    print(f"{'trazo':>6} {'accion':>7} {'primer plano':>13} {'IoU ref':>9}")
    local = to_layer(strokes, rect)
    kinds = {0: "verde", 1: "rojo", 2: "refine", 3: "borra"}
    for i in range(1, len(local) + 1):
        # Cada prefijo (1, 1+2, 1+2+3…) pasa por accumulate.accumulate, la
        # MISMA función del plugin: si aquí sube y en Krita baja, el problema
        # no es del criterio de acumulación.
        try:
            acc_bytes, calls = accumulate.accumulate(
                local[:i], w, h, lambda pts: sam2_client.segment(raw, w, h, pts)
            )
        except ValueError as e:
            print(f"{i:>6} {kinds.get(local[i - 1][0], '?'):>7}   —  {e}")
            continue
        acc = np.frombuffer(acc_bytes, dtype=np.uint8) > 127
        fg = acc.mean() * 100.0
        iou = float("nan")
        if ref is not None:
            r2 = ref.reshape(-1)
            inter = np.logical_and(acc, r2).sum()
            union = np.logical_or(acc, r2).sum()
            iou = inter / union if union else 0.0
        mask_img = Image.fromarray((acc.reshape(h, w) * 255).astype(np.uint8))
        mask_img.save(out / f"mascara_{i}.png")
        shaded = Image.composite(rgb, Image.new("RGB", (w, h), (30, 30, 30)), mask_img)
        shaded.save(out / f"vista_{i}.png")
        kind = local[i - 1][0]
        print(f"{i:>6} {kinds.get(kind, '?'):>7} {fg:>12.1f} % {iou:>9.3f}  ({calls} sam)")
    print(f"\nmáscaras y vistas en {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
