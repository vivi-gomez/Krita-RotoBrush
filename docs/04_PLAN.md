# Plan por hitos

Cada hito termina con una prueba reproducible y queda anotado en `DIARIO.md`.
Nada se da por bueno “porque compila”.

## M0 — Planificación (en curso)

- Documentos, estructura, inventario de modelos y librerías.
- **Salida:** repo ordenado, sin código, con decisiones cerradas.

## M1 — Motor de segmentación — hecho (2026-11-08)

- Crate `core/roto_brush_core` que envuelve los crates de EffectCraft.
- CLI de prueba: imagen + puntos → PNG con alfa.
- **Salida:** máscara correcta sobre `assets/` con FG, FG+BG y Refine; tiempos
  medidos en CPU.
- **Riesgo:** que el graph-cut no discrimine bien con MobileSAM (ya pasó en el
  intento anterior). Mitigación: probar primero con el CLI de EffectCraft como
  referencia y comparar máscaras.

## M2 — Puente Python ↔ Rust

- API C estable + carga con `ctypes` desde un Python 3.13 de prueba.
- **Salida:** mismo resultado que el CLI, sin numpy, con buffers de bytes.

## M3 — Herramienta en el toolbox

- Shim C++ por versión (Krita 6 primero, luego 5) y carga desde el plugin Python.
- **Salida:** el botón aparece en la caja de herramientas y activa el pincel.
- **Riesgo:** ABI/cabeceras (KF5/KF6, Qt 5.15.7 vs 6.8.0). Mitigación: plan B de
  D-004 si no se estabiliza en un tiempo acotado.

## M4 — Flujo completo

- Docker con ajustes, trazos acumulativos, Alt=BG, Refine Edge, Deshacer.
- Aplicar en la misma capa con copia de seguridad en memoria.
- **Salida:** prueba manual en Krita 5 y 6 sobre `assets/`, sin congelaciones ni
  capas nuevas.

## M5 — Calidad y entrega

- Ajuste de valores por defecto (feather, smooth, decontaminate).
- Casos: pelo, ropa con fondo similar, bordes duros.
- Empaquetado, `install.sh`/`uninstall.sh`, guía de usuario.
- **Salida:** release instalable desde GitHub.

## Regla de parada

Si un hito falla dos veces por la misma causa, se documenta el bloqueo y se
cambia de estrategia antes de seguir escribiendo código.
