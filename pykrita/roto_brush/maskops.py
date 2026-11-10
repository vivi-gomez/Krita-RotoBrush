"""Operaciones de máscara binaria (0 o 255) sin dependencias externas.

Las usan compute.py y el arnés de pruebas; se manipulan como enteros
grandes, así que unir, restar y dilatar cuestan milisegundos por mega.
"""

from math import isqrt


def _merge(a: bytes, b: bytes, union: bool) -> bytes:
    """Une (OR) o interseca (AND) dos alfas binarios del worker (0 o 255)."""
    if len(a) != len(b):
        raise ValueError(f"alfas de tamaños distintos: {len(a)} y {len(b)}")
    x, y = int.from_bytes(a, "little"), int.from_bytes(b, "little")
    return (x | y if union else x & y).to_bytes(len(a), "little")


def _subtract(a: bytes, reg: bytes) -> bytes:
    """Quita de un alfa binario la zona (0/255) que le pasa uno."""
    if len(a) != len(reg):
        raise ValueError(f"alfas de tamaños distintos: {len(a)} y {len(reg)}")
    full = (1 << (len(a) * 8)) - 1
    x = int.from_bytes(a, "little")
    y = int.from_bytes(reg, "little")
    return (x & (full ^ y)).to_bytes(len(a), "little")


def _erase_region(pts, radius, w: int, h: int) -> bytes:
    """Bytes con 255 en el barrido del trazo: la goma resta SOLO esa zona.

    SAM no sabe "quitar una zona": con puntos negativos devuelve solo un
    trozo del personaje y la máscara colapsaba. El borrado local es
    predecible y no depende de la suerte de los candidatos."""
    r = max(16, int(1.5 * float(radius)))
    reg = bytearray(w * h)
    for px, py in pts:
        cx, cy = int(px), int(py)
        if 0 <= cx < w and reg[cy * w + cx]:
            continue  # punto ya barrido
        for y in range(max(0, cy - r), min(h, cy + r + 1)):
            dy = y - py
            dx = isqrt(max(0, r * r - int(dy * dy)))
            x0, x1 = max(0, cx - dx), min(w, cx + dx + 1)
            if x0 < x1:
                reg[y * w + x0:y * w + x1] = b"\xff" * (x1 - x0)
    return bytes(reg)


def _dilate1(a: bytes, w: int) -> bytes:
    """Dilata 1 px con vecindad completa (caja 3x3) un alfa binario (0 o 255),
    a nivel de bits.

    SAM 2.1 recorta sistemáticamente el pelo difuso de los bordes; 1 px de
    margen recupera IoU contra el alfa de referencia sin pasarse de largo.
    Las máscaras de desplazamiento evitan que una fila coma a la vecina."""
    h = len(a) // w
    x = int.from_bytes(a, "little")
    not_last = int.from_bytes((bytes([255] * (w - 1) + [0])) * h, "little")
    not_first = int.from_bytes((bytes([0]) + bytes([255] * (w - 1))) * h, "little")
    one, rw = 8, w * 8
    right, left = (x & not_last) << one, (x & not_first) >> one
    v = x | right | left | (x << rw) | (x >> rw)
    v |= (right << rw) | (right >> rw) | (left << rw) | (left >> rw)
    return (v & ((1 << (len(a) * 8)) - 1)).to_bytes(len(a), "little")
