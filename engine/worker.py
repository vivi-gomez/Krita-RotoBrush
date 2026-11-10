"""Servidor local de SAM 2.1 para el plugin Roto Brush.

Protocolo: 4 bytes de longitud (big-endian) + JSON.
Petición:  {"cmd":"segment","w":W,"h":H,"image":"<base64 RGBA/BGRA>","bgra":true,
            "points":[[x,y,1|0],...],"box":[x0,y0,x1,y1] | null}
Respuesta: {"ok":true,"alpha":"<base64 w*h>","score":0.93,"ms":1200}
           {"ok":false,"error":"..."}

Uso:  .engine/venv/bin/python engine/worker.py --port 8765
"""

import argparse
import base64
import json
import socket
import socketserver
import struct
import time

import numpy as np
import torch
from PIL import Image


class Engine:
    def __init__(self, ckpt: str, config: str):
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        model = build_sam2(config, ckpt, device=device)
        self.predictor = SAM2ImagePredictor(model)

    def segment(self, image: np.ndarray, points, box):
        """image: RGB uint8 (h, w, 3). Devuelve alfa uint8 (h, w) y score."""
        with torch.inference_mode():
            self.predictor.set_image(image)
            masks, scores, _ = self.predictor.predict(
                point_coords=None if not points else np.array([p[:2] for p in points]),
                point_labels=None if not points else np.array([p[2] for p in points]),
                box=None if box is None else np.array(box),
                multimask_output=True,
            )
        # Elegir candidato: el mayor que contenga los puntos de primer plano y no
        # cubra casi toda la imagen (los scores de SAM no son fiables aquí).
        fg = [(int(p[0]), int(p[1])) for p in points if p[2] == 1]
        h, w = masks.shape[1], masks.shape[2]
        total = float(h * w)
        best, best_area = int(np.argmax(scores)), 0.0
        for i, mk in enumerate(masks):
            area = float(mk.mean())
            if area < 0.001 or area > 0.9:
                continue
            if fg and not all(0 <= x < w and 0 <= y < h and mk[y, x] > 0.5 for x, y in fg):
                continue
            if area > best_area:
                best, best_area = i, area
        alpha = (masks[best] * 255).astype(np.uint8)
        return alpha, float(scores[best])


def read_msg(sock) -> dict:
    header = sock.recv(4)
    if len(header) < 4:
        raise ConnectionError("sin cabecera")
    (size,) = struct.unpack(">I", header)
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("cortado")
        data += chunk
    return json.loads(data.decode("utf-8"))


def send_msg(sock, obj) -> None:
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(struct.pack(">I", len(data)) + data)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        engine = self.server.engine
        try:
            req = read_msg(self.request)
        except Exception:  # noqa: BLE001
            return
        if req.get("cmd") == "ping":
            send_msg(self.request, {"ok": True, "device": engine.device})
            return
        try:
            w, h = int(req["w"]), int(req["h"])
            raw = base64.b64decode(req["image"])
            arr = np.frombuffer(raw, np.uint8).reshape((h, w, 4))
            if req.get("bgra"):
                rgb = arr[:, :, [2, 1, 0]]
            else:
                rgb = arr[:, :, :3]
            t0 = time.time()
            alpha, score = engine.segment(rgb, req.get("points") or [], req.get("box"))
            ms = int((time.time() - t0) * 1000)
            send_msg(self.request, {
                "ok": True,
                "alpha": base64.b64encode(alpha.tobytes()).decode("ascii"),
                "score": score,
                "ms": ms,
            })
        except Exception as e:  # noqa: BLE001
            send_msg(self.request, {"ok": False, "error": repr(e)})


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--model", default=".engine/models/sam2.1_hiera_large.pt")
    ap.add_argument("--config", default="configs/sam2.1/sam2.1_hiera_l.yaml")
    args = ap.parse_args()

    engine = Engine(args.model, args.config)
    server = Server((args.host, args.port), Handler)
    server.engine = engine
    print(f"SAM 2.1 listo en {args.host}:{args.port} ({engine.device})", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
