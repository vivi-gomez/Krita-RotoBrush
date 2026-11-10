# Herramienta nativa (C++)

Shim mínimo para que la herramienta aparezca en la caja de herramientas de
Krita. Ver `docs/06_TOOLBOX_NATIVO.md`.

## Piezas previstas

| Pieza | Responsabilidad |
|---|---|
| `CMakeLists.txt` | Un objetivo por versión de Krita |
| `src/plugin.cpp` | `load_roto_brush_plugin()` (extern "C") |
| `src/tool.cpp` | Captura de trazos y dibujo del trazo |
| `src/factory.h` | Factoría de herramienta |
| `src/bridge.h` | Puente hacia el docker / motor |

## Compilación

- K5: Qt 5.15 + KF5, contra `libkritaui.so.20`.
- K6: Qt 6.8 + KF6, contra `libkritaui.so.21`.
- Enlazado con las librerías del AppImage correspondiente; `RPATH=$ORIGIN`.
- Cabeceras de Krita y KF en `.deps/` (fuera de Git).
