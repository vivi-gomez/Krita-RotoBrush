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


def _erase_region(pts, radius, w: int, h: int, factor: float = 1.5, floor: int = 16) -> bytes:
    """Bytes con 255 en el barrido del trazo: la goma resta SOLO esa zona.

    SAM no sabe "quitar una zona": con puntos negativos devuelve solo un
    trozo del personaje y la máscara colapsaba. El borrado local es
    predecible y no depende de la suerte de los candidatos.

    `factor` y `floor` ajustan el radio efectivo: la goma usa el barrido
    justo (1,5 × pincel) y Refine necesita una envolvente más ancha para
    atrapar el borde que rodea el trazo."""
    r = max(floor, int(factor * float(radius)))
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


def _flood(seed: bytes, mask: bytes, w: int) -> bytes:
    """Componente conexa de `mask` (4-vecindad) que toca el barrido `seed`.

    Inundación a nivel de bits: la semilla se desplaza arriba, abajo, a
    izquierda y derecha, se OR-combina y se recorta a la máscara, en bucle
    hasta que nada crece. Las máscaras de borde de fila (como en _dilate1)
    evitan que una fila coma a la vecina, y la cota por bit-length recorta
    enteros para que las vueltas sean las del diámetro de la componente.
    Con esto, un trazo rojo que roza la mejilla se lleva la mejilla ENTERA,
    no una banda de 32 px."""
    if len(seed) != len(mask):
        raise ValueError(f"alfas de tamaños distintos: {len(seed)} y {len(mask)}")
    n = len(mask)
    if n % w:
        raise ValueError(f"alfas de {n} bytes que no caben en filas de {w} px")
    m_int = int.from_bytes(mask, "little")
    x = int.from_bytes(seed, "little") & m_int
    if not x:
        return b"\x00" * n
    not_last = int.from_bytes((bytes([255] * (w - 1) + [0])) * (n // w), "little")
    not_first = int.from_bytes((bytes([0]) + bytes([255] * (w - 1))) * (n // w), "little")
    one, rw = 8, w * 8
    while True:
        cap = (1 << min(n * 8, x.bit_length() + rw + one)) - 1
        grow = x | ((x & not_last) << one) | ((x & not_first) >> one)
        grow |= ((x << rw) | (x >> rw)) & cap
        grow &= m_int
        if grow == x:
            return x.to_bytes(n, "little")
        x = grow


def _erase_component(mask: bytes, pts, radius, w: int, h: int) -> bytes:
    """Goma con semántica de cubo: quita de la máscara la componente conexa
    que toca el barrido del trazo (y solo esa)."""
    reg = _erase_region(pts, radius, w, h)
    comp = _flood(reg, mask, w)
    return _subtract(mask, comp)


def _neighborhood(pts, radius, w: int, h: int) -> bytes:
    """Envolvente barrida por un trazo Refine: la única zona donde su
    resultado puede entrar en la máscara.

    Es más ancha que la goma (2,5 × pincel, mínimo 40 px) porque Refine
    pide justo el borde de lo pintado, y el borde vivo queda fuera del
    trazo."""
    return _erase_region(pts, radius, w, h, factor=2.5, floor=40)


def _refine_local(mask: bytes, fresh: bytes, pts, radius, w: int, h: int) -> bytes:
    """Refine local: de lo que SAM proponga para este trazo solo se acepta lo
    que cae en su vecindario, y eso se UNE a la máscara.

    Con el contexto global Refine contaminaba todo el fondo: SAM elegía otro
    candidato y la unión pegaba la basura. Recortado al vecindario del trazo,
    Refine solo puede ensanchar el borde que el usuario está señalando."""
    return _merge(mask, _merge(fresh, _neighborhood(pts, radius, w, h), False), True)


def _scale_alpha(orig: bytes, alpha: bytes, w: int, h: int, bpc: int = 1) -> bytes:
    """Multiplica el canal alfa de la capa por la máscara (0..255).

    `bpc` son los bytes por canal: 1 en RGBA U8 y 2 en RGBA U16. Con 16 bits
    trabaja sobre `array('H')`, que usa el orden de bytes de la máquina, el
    mismo que devuelve `node.pixelData()`. Lo que entra y lo que sale tiene la
    misma longitud: solo cambian los alfas, el color no se toca."""
    n = w * h
    if len(alpha) != n:
        raise ValueError(f"la máscara no cuadra: {len(alpha)} != {n}")
    if len(orig) != n * 4 * bpc:
        raise ValueError(f"la capa no cuadra: {len(orig)} != {n * 4 * bpc}")
    if bpc == 1:
        out = bytearray(orig)
        for i in range(n):
            a = out[i * 4 + 3]
            if a and alpha[i] != 255:
                out[i * 4 + 3] = (a * alpha[i]) // 255
        return bytes(out)
    if bpc != 2:
        raise ValueError(f"profundidad desconocida: {bpc} bytes por canal")
    import array

    vals = array.array("H")
    vals.frombytes(orig)
    ch = vals[3::4]
    for i in range(n):
        m = alpha[i]
        if m != 255:
            ch[i] = (ch[i] * m) // 255
    vals[3::4] = ch
    return vals.tobytes()


def _to_rgba8(px: bytes, bpc: int) -> bytes:
    """Baja una capa RGBA de 16 bits a 8 bits tomando el byte alto de cada
    canal. Sirve para el MOTOR (SAM solo quiere ver la foto); para escribir en
    la capa se usa _scale_alpha, que respeta los 16 bits."""
    if bpc == 1:
        return px
    return px[bpc - 1::bpc]


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
