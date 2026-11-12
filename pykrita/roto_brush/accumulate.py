"""Cómo se convierten N trazos en UNA máscara con SAM 2.1.

Vive aparte de compute.py para que el arnés de pruebas (tests/
replay_recording.py) ejecute EXACTAMENTE el mismo criterio que el plugin:
así una prueba fuera de Krita vale de verdad.

Reglas:
  verde (FG)     -> se UNE su máscara, con todo el contexto verde acumulado.
  refine         -> se UNE solo dentro del vecindario del trazo (v0.5).
  rojo / borra   -> se va la componente conexa que toca el barrido (goma).
  goma persistente -> lo quitado con rojo no vuelve con el siguiente verde,
                    salvo bajo el pincel de ese trazo nuevo.
"""

try:  # dentro del paquete del plugin
    from .maskops import (
        _erase_component,
        _merge,
        _neighborhood,
        _refine_local,
        _subtract,
    )
except ImportError:  # cargado como módulo suelto por el arnés
    from maskops import (
        _erase_component,
        _merge,
        _neighborhood,
        _refine_local,
        _subtract,
    )

FG, BG, REFINE, REFINE_ERASE = 0, 1, 2, 3


def sample(points, label: int, cap: int = 12):
    """Muestrea ~`cap` puntos de un trazo y los marca con `label`.

    1 = primer plano, 0 = fondo. Pocos puntos bastan: SAM generaliza con la
    silueta y cada punto extra cuesta tiempo en el worker."""
    step = max(1, len(points) // cap)
    chosen = points[::step]
    if chosen[-1] != points[-1]:
        chosen.append(points[-1])
    return [[round(float(p[0]), 1), round(float(p[1]), 1), label] for p in chosen]


def accumulate(strokes, w: int, h: int, segment):
    """Acumula los trazos y devuelve (máscara, llamadas a SAM).

    `segment(puntos)` devuelve el alfa (0/255, w*h bytes) que propone SAM 2.1
    para esa lista de puntos; quien llama decide cómo hablar con el motor.
    Sin trazos verdes de primer plano no hay nada que segmentar."""
    acc = None
    erased = None  # lo que el usuario quitó con rojo: es persistente
    green_pts = []
    calls = 0
    for kind, radius, pts, _f in strokes:
        if not pts:
            continue
        if kind == FG:
            # Contexto completo: TODOS los puntos verdes hasta el trazo
            # actual; si algún cálculo colapsa, la unión no lo pierde.
            green_pts.extend(sample(pts, 1))
            mask = segment(list(green_pts))
            calls += 1
            if acc is None:
                acc = mask
            else:
                # Lo borrado con rojo NO resucita al calcular el siguiente
                # verde, salvo bajo el pincel del trazo nuevo: ahí el usuario
                # está diciendo que eso sí es personaje (queja 3).
                acc = _merge(acc, mask, True)
                if erased is not None:
                    fuera = _subtract(erased, _neighborhood(pts, radius, w, h))
                    acc = _subtract(acc, fuera)
        elif kind == REFINE:
            # Refine local (v0.5): SOLO los puntos de este trazo, y de su
            # resultado no sale del vecindario barrido. Con contexto global
            # SAM elegía otro candidato y la unión pegaba basura por el fondo.
            fresh = segment(sample(pts, 1))
            calls += 1
            acc = (
                _refine_local(acc, fresh, pts, radius, w, h)
                if acc is not None
                else _merge(fresh, _neighborhood(pts, radius, w, h), False)
            )
            if erased is not None:
                acc = _subtract(acc, erased)
        elif kind in (BG, REFINE_ERASE):
            # SAM no sabe "quitar una zona": con puntos negativos devuelve
            # solo un fragmento. La goma funciona como el cubo: se va la
            # componente conexa ENTERA que toca el barrido del trazo.
            if acc is None:
                continue
            antes = acc
            acc = _erase_component(acc, pts, radius, w, h)
            erased = _merge(erased, _subtract(antes, acc), True) if erased else _subtract(antes, acc)
    if acc is None:
        raise ValueError("hace falta al menos un trazo verde")
    return acc, calls
