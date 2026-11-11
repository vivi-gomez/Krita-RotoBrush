"""Prueba de la goma por componente conexa (máscaras binarias).

Cubre _flood y _erase_component de maskops.py: el rojo debe llevarse la
componente ENTERA que toca y no puede saltar por las esquinas ni por el
borde de fila. Python puro, sin Krita ni SAM:

Ejecutar:  python3 tests/test_maskops.py
"""

import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "maskops", ROOT / "pykrita" / "roto_brush" / "maskops.py"
)
maskops = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(maskops)

ON, OFF = 255, 0


def grid(rows):
    """Filas de '.' y '#' -> bytes de máscara binaria (w, h, bytes)."""
    h, w = len(rows), len(rows[0])
    b = bytearray(w * h)
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            b[y * w + x] = ON if c == "#" else OFF
    return w, h, bytes(b)


def show(mask, w, h):
    return "\n".join(
        "".join("#" if mask[y * w + x] else "." for x in range(w))
        for y in range(h)
    )


def cells(points, w, h):
    b = bytearray(w * h)
    for x, y in points:
        b[y * w + x] = ON
    return bytes(b)


def check(name, cond, detail=""):
    print(f"  {'OK ' if cond else 'FALLO'} {name} {detail}")
    return cond


def main() -> int:
    ok = True

    print("_flood:")
    w, h, m = grid(["######", "##....", "##....", "###..#", "######"])
    got = maskops._flood(cells([(0, 0)], w, h), m, w)
    ok &= check("inunda la componente entera", got == m)

    w, h, m = grid(["#.#", ".#.", "#.#"])
    got = maskops._flood(cells([(0, 0)], w, h), m, w)
    ok &= check("no salta por la esquina (4-vecindad)", got == cells([(0, 0)], w, h))

    w, h, m = grid(["##..", "..##"])
    got = maskops._flood(cells([(1, 0)], w, h), m, w)
    ok &= check(
        "no cruza el borde de fila",
        got == cells([(0, 0), (1, 0)], w, h),
        f"\n{show(got, w, h)}",
    )

    w, h, m = grid(["##..", "##..", "..##"])
    got = maskops._flood(cells([(3, 0)], w, h), m, w)  # semilla sobre hueco
    ok &= check("semilla fuera de la máscara no inunda nada", got.count(ON) == 0)

    try:
        maskops._flood(b"\xff" * 7, b"\xff" * 7, 4)  # 7 no cabe en filas de 4
        ok &= check("rechaza máscaras que no caben en filas enteras", False)
    except ValueError:
        ok &= check("rechaza máscaras que no caben en filas enteras", True)

    print("_erase_component (goma tipo cubo):")
    # Rejilla de 60x60 con dos componentes alejadas (el barrido mínimo de la
    # goma tiene radio 16 px): se va la tocada y la otra debe quedar intacta.
    rows = [["."] * 60 for _ in range(60)]
    for y in range(0, 3):            # componente tocada: 3x3 en el origen
        for x in range(0, 3):
            rows[y][x] = "#"
    for y in range(40, 46):          # componente lejana: 6x6 en (30, 40)
        for x in range(30, 36):
            rows[y][x] = "#"
    w, h, m = grid(["".join(r) for r in rows])
    got = maskops._erase_component(m, [(1.0, 1.0)], 8, w, h)
    left = sum(1 for y in range(40, 46) for x in range(30, 36) if got[y * w + x])
    ok &= check(
        "se va la componente tocada entera y la otra intacta",
        sum(1 for y in range(3) for x in range(3) if got[y * w + x]) == 0
        and left == 36,
    )

    # Trazo rojo que toca el borde de una mancha (el barrido tiene radio 16
    # y solapa unos píxeles): la mancha debe irse ENTERA (queja 3).
    rows = [["."] * 40 for _ in range(20)]
    for y in range(6, 14):           # mancha de 8x8 en x=20..27
        for x in range(20, 28):
            rows[y][x] = "#"
    w, h, m = grid(["".join(r) for r in rows])
    pts = [(float(x), 10.0) for x in range(10, 20)]  # barrido termina en x=19
    got = maskops._erase_component(m, pts, 8, w, h)  # radio 8 -> toca x>=12
    ok &= check("rozar la mancha la borra completa", got.count(ON) == 0)

    print("rendimiento (1344x1344 con mancha de ~200 px de diámetro):")
    w = h = 1344
    m = bytearray(w * h)
    for y in range(500, 700):
        m[y * w + 500:y * w + 700] = b"\xff" * 200
    m = bytes(m)
    seed = [(float(x), 600.0) for x in range(480, 505)]
    t0 = time.time()
    got = maskops._erase_component(m, seed, 8, w, h)
    dt = (time.time() - t0) * 1000.0
    ok &= check("borrado completo", got.count(ON) == 0)
    ok &= check(f"tiempo {dt:.0f} ms < 2000 ms", dt < 2000.0)

    print("todo correcto" if ok else "HAY FALLOS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
