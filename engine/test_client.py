"""Prueba del servidor SAM 2.1 sin Krita."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pykrita"))

import numpy as np
from PIL import Image

from roto_brush import sam2_client


def main() -> int:
    img = Image.open(sys.argv[1]).convert("RGB")
    rgb = np.asarray(img)
    h, w = rgb.shape[:2]
    bgra = np.dstack([rgb[:, :, ::-1], np.full((h, w), 255, np.uint8)])
    points = [[430, 780, 1], [470, 820, 1], [50, 50, 0], [600, 970, 0]]
    alpha = sam2_client.segment(bgra.tobytes(), w, h, points)
    a = np.frombuffer(alpha, np.uint8).reshape(h, w)
    out = np.dstack([rgb, a])
    Image.fromarray(out, "RGBA").save(sys.argv[2])
    print("ok", sys.argv[2], "alfa medio", a.mean())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
