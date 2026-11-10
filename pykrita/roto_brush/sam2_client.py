"""Cliente del servidor SAM 2.1 (engine/worker.py) para el plugin."""

import base64
import json
import os
import socket
import struct

HOST = os.environ.get("ROTO_BRUSH_SAM2_HOST", "127.0.0.1")
PORT = int(os.environ.get("ROTO_BRUSH_SAM2_PORT", "8765"))


def _recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("conexión cerrada")
        data += chunk
    return data


def _send(sock, obj) -> None:
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(struct.pack(">I", len(data)) + data)


def _recv(sock) -> dict:
    (size,) = struct.unpack(">I", _recv_exact(sock, 4))
    return json.loads(_recv_exact(sock, size).decode("utf-8"))


def ping(timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=timeout) as s:
            _send(s, {"cmd": "ping"})
            return bool(_recv(s).get("ok"))
    except Exception:  # noqa: BLE001
        return False


def segment(rgba: bytes, w: int, h: int, points, box=None, timeout: float = 120.0) -> bytes:
    """Devuelve el alfa (w*h bytes). `points`: [[x, y, 1|0], ...]."""
    with socket.create_connection((HOST, PORT), timeout=timeout) as s:
        _send(s, {
            "cmd": "segment",
            "w": w,
            "h": h,
            "bgra": True,
            "image": base64.b64encode(rgba).decode("ascii"),
            "points": points,
            "box": box,
        })
        resp = _recv(s)
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error", "fallo del motor SAM 2.1"))
    return base64.b64decode(resp["alpha"])
