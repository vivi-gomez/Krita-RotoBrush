"""Prueba las REGLAS de acumulación (accumulate.py) con un SAM de mentirija.

Aquí no importa cuán buena sea la máscara: importa que el criterio sea el que
prometimos al usuario, y que las quejas de la sesión 7 no vuelvan:

  1. el segundo trazo verde SE SUMA al primero (no lo borra);
  2. el rojo quita la mancha entera que toca;
  3. lo quitado con rojo NO resucita con el siguiente verde, salvo que se
     pinte verde ENCIMA;
  4. el refine no mancha el fondo aunque SAM proponga el lienzo entero;
  5. sin verde no hay máscara (error claro).

Python puro, sin Krita ni GPU:   python3 tests/test_accumulate.py
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pykrita" / "roto_brush"))
_spec = importlib.util.spec_from_file_location(
    "maskops", ROOT / "pykrita" / "roto_brush" / "maskops.py"
)
maskops = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(maskops)
sys.modules["maskops"] = maskops
_spec2 = importlib.util.spec_from_file_location(
    "accumulate", ROOT / "pykrita" / "roto_brush" / "accumulate.py"
)
accumulate = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(accumulate)

W = H = 120
FG, BG, REFINE = 0, 1, 2


def line(x0, y0, x1, y1, step=3):
    n = max(2, int(max(abs(x1 - x0), abs(y1 - y0)) / step) + 1)
    return [[x0 + (x1 - x0) * i / (n - 1), y0 + (y1 - y0) * i / (n - 1)] for i in range(n)]


def px(mask, x, y):
    return mask[y * W + x] > 127


def count(mask):
    return sum(1 for b in mask if b > 127)


def fake_segment(pts):
    """SAM de juguete: un cuadrado de +/-16 px alrededor de cada punto verde."""
    verdes = [(p[0], p[1]) for p in pts if len(p) < 3 or p[2] == 1]
    b = bytearray(W * H)
    for x, y in verdes:
        x0, x1 = max(0, int(x) - 16), min(W, int(x) + 17)
        y0, y1 = max(0, int(y) - 16), min(H, int(y) + 17)
        for yy in range(y0, y1):
            b[yy * W + x0:yy * W + x1] = b"\xff" * (x1 - x0)
    return bytes(b)


def check(name, cond, detail=""):
    print(f"  {'OK ' if cond else 'FALLO'} {name} {detail}")
    return cond


def main() -> int:
    ok = True
    verde_izq = (FG, 8.0, line(20, 30, 30, 30), -1.0)
    verde_der = (FG, 8.0, line(90, 80, 100, 80), -1.0)
    rojo_izq = (BG, 8.0, line(20, 30, 30, 30), -1.0)

    print("queja 2: el segundo verde se suma al primero")
    m2, calls = accumulate.accumulate([verde_izq, verde_der], W, H, fake_segment)
    ok &= check("mantiene las dos manchas", px(m2, 25, 30) and px(m2, 95, 80))
    ok &= check("no es solo la última", count(m2) > count(
        accumulate.accumulate([verde_der], W, H, fake_segment)[0]))
    ok &= check(f"una llamada por trazo ({calls} = 2)", calls == 2)

    print("queja 3: lo borrado con rojo no resucita")
    m3, _ = accumulate.accumulate([verde_izq, verde_der, rojo_izq], W, H, fake_segment)
    ok &= check("el rojo se lleva la mancha tocada entera", not px(m3, 20, 30) and not px(m3, 30, 30))
    ok &= check("la otra mancha sigue viva", px(m3, 95, 80))
    m4, _ = accumulate.accumulate(
        [verde_izq, verde_der, rojo_izq, (FG, 8.0, line(90, 40, 100, 40), -1.0)],
        W, H, fake_segment,
    )
    ok &= check("un verde lejos no la trae de vuelta", not px(m4, 25, 30))
    m5, _ = accumulate.accumulate(
        [verde_izq, verde_der, rojo_izq, (FG, 8.0, line(20, 30, 30, 30), -1.0)],
        W, H, fake_segment,
    )
    ok &= check("pintar verde ENCIMA de lo borrado la recupera", px(m5, 25, 30))

    print("refine local: no mancha el fondo")
    def sam_dramatico(pts):
        # Si el trazo es de refine (puntos en y=70), SAM propone TODO el lienzo.
        if pts and all(p[1] > 60 for p in pts[:4]):
            return b"\xff" * (W * H)
        return fake_segment(pts)

    base, _ = accumulate.accumulate([verde_izq], W, H, sam_dramatico)
    refine = (REFINE, 18.0, line(55, 70, 75, 70), -1.0)
    band = maskops._neighborhood(refine[2], refine[1], W, H)
    m6, _ = accumulate.accumulate([verde_izq, refine], W, H, sam_dramatico)
    ok &= check("dentro del vecindario del refine sí entra", px(m6, 65, 72))
    ok &= check("lejos del refine no cambia nada", px(m6, 25, 30) and not px(m6, 110, 110))
    ok &= check(
        "fuera del vecindario la máscara es idéntica a la de antes",
        all((m6[i] > 127) == (base[i] > 127) for i in range(W * H) if not band[i]),
    )

    print("sin verde no hay máscara")
    try:
        accumulate.accumulate([rojo_izq], W, H, fake_segment)
        ok &= check("rojo solo da error claro", False)
    except ValueError:
        ok &= check("rojo solo da error claro", True)

    print("todo correcto" if ok else "HAY FALLOS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
