# Modelos y librerías

## Modelo usado

| Modelo | Tamaño | SHA-256 | Licencia | Uso |
|---|---|---|---|---|
| `mobile_sam.pt` | 40 728 226 B | `6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f` | Apache-2.0 | Segmentación (MobileSAM) |

- Ruta por defecto: `~/.config/effectcraft/models/mobile_sam.pt` (la carpeta de
  EffectCraft), configurable con `ROTO_BRUSH_MODEL` y desde el docker.
- Se verifica el SHA-256 al cargar; si no coincide, se avisa y no se usa.
- **Nunca** se sube al repositorio (ver `.gitignore`).

## Modelos descartados

| Modelo | Motivo |
|---|---|
| `sam2.1-hiera-large.safetensors` | No soportado por los crates de EffectCraft; fuera de alcance |
| `face_landmarker.task` | Solo para tracking de caras; no se usa |

## Librerías

### Rust (motor)

| Crate | Versión | Licencia |
|---|---|---|
| `effectcraft-track` | 0.9.2 | MIT OR Apache-2.0 |
| `effectcraft-segment` | 0.9.2 | MIT OR Apache-2.0 |
| `effectcraft-raster` | 0.9.2 | MIT OR Apache-2.0 |

Herramienta: Rust 1.95.0 (el workspace de EffectCraft exige `rust-version 1.95`).

### Krita

| Krita | Python | Qt | KF | Bindings |
|---|---|---|---|---|
| 5.3.x | 3.13 | 5.15.7 | KF5 | PyQt5 5.15.11 |
| 6.x | 3.13 | 6.8.0 | KF6 | PyQt6 6.8.1 |

Ninguna trae `numpy`: por eso el cálculo no va en Python.

### Entorno de desarrollo

Qt 5.15.18 y Qt 6.10.2 del sistema sirven para M1/M2; para el shim de M3 hace
falta Qt 6.8.0 (el de Krita 6) y cabeceras de KF5/KF6.
