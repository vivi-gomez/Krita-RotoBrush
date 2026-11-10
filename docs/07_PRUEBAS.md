# Pruebas

## Regla

Cada prueba deja evidencia: comando, resultado y salida guardada. Lo que no se
ha ejecutado se marca como pendiente, nunca como aprobado.

## Niveles

### N1 — Motor (sin Krita)

- Comando del CLI sobre `assets/Krea2_turbo_style_reference_00001_.png`.
- Casos: solo FG, FG+BG, Refine Edge.
- Se guarda el PNG del alfa y métricas (tiempo, porcentaje de primer plano).
- **Criterio:** el personaje queda completo y el fondo fuera; sin cuadrados ni
  bloques.

### N2 — Puente Python

- Cargar la biblioteca y repetir el caso N1 desde Python 3.13 sin numpy.
- **Criterio:** máscara idéntica al CLI (mismo hash de alfa).

### N3 — Carga en Krita

- Abrir Krita 6 (AppImage) y Krita 5; comprobar en el log del plugin que el
  docker y la herramienta se registran.
- **Criterio:** sin tracebacks, botón visible en el toolbox.

### N4 — Interacción

- Pulsar el botón, pintar FG/BG/Refine, cambiar ajustes, Aplicar, Deshacer.
- Comprobar que la imagen original no se mancha durante los trazos y que la UI
  no se congela.
- **Criterio:** el resultado aparece en la capa original y se puede restaurar.

## Entorno de prueba

- Krita 5.3.x y Krita 6.0.0-beta1 (AppImage), pantalla X disponible.
- Imagen de prueba: 1024×1024 RGB.
- Modelo: `mobile_sam.pt` verificado por SHA-256.

## Limitaciones conocidas

- Sin GPU: todo se mide en CPU (48 hilos).
- La AppImage de Krita 5 necesita `LD_PRELOAD` de su `libglib` en este equipo.
- La validación visual requiere ojos: se apoya en capturas de pantalla.

## Resultados

| Fecha | Prueba | Resultado |
|---|---|---|
| 2026-11-08 | Acceso de escritura al proyecto | OK |
| 2026-11-08 | Inventario de modelos y librerías | OK |
| 2026-11-08 | Unitarias del motor | 4/4 OK |
| 2026-11-08 | Motor (N1) con trazos separados | OK (model mejor que classic) |
| 2026-11-08 | Refine Edge | Actúa; halo con valores altos |
| 2026-11-08 | Motor (N1) con una sola polilínea | **Falló** (huecos en diagonal) — corregido usando trazos separados |

| 2026-11-08 | API C desde ctypes (sintética) | OK |
| 2026-11-08 | Harness del plugin con PyQt5 y PyQt6 | 5/5 y 5/5 |
| 2026-11-08 | Arranque de Krita 6 extraída | **Falló** (sin `PYTHONHOME`; y la pantalla `:0` se perdió) |
| 2026-11-08 | Plugin instalado en el perfil | OK; falta validación visual |

| 2026-11-08 | Harness del plugin (6 comprobaciones) | 6/6 con PyQt5 y 6/6 con PyQt6 |
| 2026-11-08 | Instalación en el perfil | OK (corregido enlace roto de la librería) |
| 2026-11-08 | Validación visual tras el feedback | Pendiente: la pantalla `:0` no está disponible |

Detalle y comandos: `tests/results/README.md`.
