# Roto Brush para Krita

Herramienta de recorte interactivo para Krita 5 y 6: se pinta sobre el personaje u
objeto que se quiere conservar y el plugin elimina el fondo **en la misma capa**,
dejándolo en transparencia. Inspirado en el Roto Brush de EffectCraft.

## Estado

- `v0.1-alpha`: plugin funcional con MobileSAM (docker, trazos, vista previa,
  undo interno). Etiqueta `v0.1-alpha`.
- **v2 en curso**: motor **SAM 2.1** en GPU mediante un proceso aparte
  (`engine/worker.py`). Ver `docs/08_MOTOR_SAM2.md`.

## Documentos

| Archivo | Contenido |
|---|---|
| `docs/01_OBJETIVO.md` | Qué hace, flujo de uso y criterios de aceptación |
| `docs/02_ARQUITECTURA.md` | Piezas y cómo se hablan |
| `docs/03_DECISIONES.md` | Decisiones tomadas y por qué |
| `docs/04_PLAN.md` | Hitos y criterios de salida |
| `docs/05_MODELOS.md` | Modelos, hashes y licencias |
| `docs/06_TOOLBOX_NATIVO.md` | Cómo se añade la herramienta al toolbox |
| `docs/07_PRUEBAS.md` | Protocolo y resultados de pruebas |
| `DIARIO.md` | Diario de trabajo, éxitos y fallos |

## Estructura

```
assets/    imagen de prueba
core/      motor Rust (segmentación + matte)
native/    herramienta nativa C++ para el toolbox
pykrita/   plugin Python (docker + carga del motor)
tests/     pruebas automatizadas
scripts/   instalación/desinstalación
docs/      documentación
```

## Requisitos

- Krita 5.3.x (Qt 5.15, Python 3.13) y Krita 6.x (Qt 6.8, Python 3.13).
- Modelo `mobile_sam.pt` (Apache-2.0) en una ruta configurable; **no se versiona**.
- Rust estable para compilar el motor.

## Licencia y atribuciones

GPL-3.0-or-later. Terceros: `ATTRIBUTION.md`.
