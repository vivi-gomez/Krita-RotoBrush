"""Prototipo: SAM 2.1 sobre una imagen fija con puntos de primer/segundo plano.

Uso:
  .engine/venv/bin/python engine/sam2_proto.py imagen.png salida.png \
      --model .engine/models/sam2.1_hiera_large.pt --fg 450,780 --bg 50,50

Escribe un PNG con el color original y el alfa del mejor mask de SAM 2.1.
"""

import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--model", default=".engine/models/sam2.1_hiera_large.pt")
    ap.add_argument("--config", default="configs/sam2.1/sam2.1_hiera_l.yaml")
    ap.add_argument("--fg", default="")
    ap.add_argument("--bg", default="")
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGBA")
    rgb = np.asarray(img.convert("RGB"))

    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(args.config, args.model, device=device)
    predictor = SAM2ImagePredictor(model)

    points, labels = [], []
    for spec, label in ((args.fg, 1), (args.bg, 0)):
        for pair in spec.split("|"):
            if not pair.strip():
                continue
            x, y = pair.split(",")
            points.append([float(x), float(y)])
            labels.append(label)
    if not points:
        print("faltan puntos")
        return 1

    with torch.inference_mode():
        predictor.set_image(rgb)
        masks, scores, _ = predictor.predict(
            point_coords=np.array(points),
            point_labels=np.array(labels),
            multimask_output=True,
        )
    best = int(np.argmax(scores))
    alpha = (masks[best] * 255).astype(np.uint8)
    out = np.dstack([rgb, alpha])
    Image.fromarray(out, "RGBA").save(args.out)
    print(f"guardado {args.out} · score {scores[best]:.3f} · alfa medio {alpha.mean():.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
