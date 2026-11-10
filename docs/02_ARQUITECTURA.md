# Arquitectura

Tres piezas, con una frontera clara: la UI no calcula, el motor no dibuja.

## 1. Plugin Python (`pykrita/roto_brush/`)

- Registra el **docker** con la API oficial (`DockWidget` + `addDockWidgetFactory`).
- Carga la herramienta nativa con `ctypes` y una función `extern "C"` (patrón de
  Acly, ver `06_TOOLBOX_NATIVO.md`).
- Carga el motor Rust con `ctypes` (`libroto_brush_core`).
- Traduce: coordenadas de vista ↔ imagen, bytes de la capa ↔ RGB, alfa ↔ RGBA.
- Lanza el cálculo en un hilo de trabajo y aplica el resultado al terminar.

## 2. Herramienta nativa (`native/`)

- Subclase de la herramienta de Krita que captura pulsación/movimiento/suelta.
- Mantiene el estado del trazo (tipo, radio, puntos) y lo pasa a Python o
  directamente al motor.
- Dibuja el trazo en pantalla (verde FG, rojo BG, azul Refine) sin tocar la capa.
- Se compila una vez por versión de Krita (Qt5 y Qt6).

## 3. Motor Rust (`core/`)

- Depende de `effectcraft-track` 0.9.2, `effectcraft-segment` 0.9.2 y
  `effectcraft-raster` 0.9.2 (crates.io, MIT/Apache-2.0).
- `segment()`: graph-cut guiado por los trazos + probabilidad de MobileSAM como
  *prior*; devuelve la segmentación.
- `matte_alpha()`: convierte la segmentación en máscara suave (Feather, Contrast,
  Shift, Smooth, Higher Quality, Decontaminate).
- API C estable: cargar modelo, fijar trazos, calcular alfa. Sin PyTorch, sin
  numpy, sin depender de nada instalado en Krita.

## Flujo de datos

```
trazo (vista) ──► herramienta nativa ──► puntos en píxeles de imagen
                                              │
capa activa ──► RGBA ──► Python ──► motor Rust ──► alfa (w×h)
                                              │
                          capa activa ◄────────┘   (setPixelData)
```

## Decisiones de rendimiento

- La conversión de píxeles se hace en Rust; Python solo mueve buffers.
- El cálculo va en un hilo; el resultado se aplica en el hilo de UI.
- Escala de trabajo configurable (media resolución para previsualizar).

## Dónde NO se toca nada

- No se modifica la instalación de Krita ni las AppImages.
- No se escriben capas temporales en el documento.
- Los pesos de los modelos nunca entran en el repositorio.
