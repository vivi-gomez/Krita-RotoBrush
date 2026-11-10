# Herramienta en la caja de herramientas

Krita no permite crear herramientas desde Python: en `krita.pyi` (Krita 6) solo
hay `DockWidget`, `Extension`, `Filter`, `Shape`… No existe ninguna API de
herramientas. El camino que sí funciona es el de `krita-vision-tools` (Acly).

## Cómo lo hace krita-vision-tools

1. `kritavisionml.so` es un **plugin nativo de Krita** con
   `K_PLUGIN_FACTORY_WITH_JSON`, enlazado contra `kritaui`, `kritaimage` y
   `kritabasicflakes`.
2. El plugin Python solo lo carga:
   `ctypes.CDLL("lib/kritavisionml.so").load_vision_ml_plugin()`.
3. Esa función `extern "C"` crea la factoría y:
   - `KoToolRegistry::instance()->add(toolFactory)`
   - `KoToolManager::instance()->priv()->toolActionList.append(...)`
4. La inyección en el `toolActionList` es imprescindible: al cargarse tarde (vía
   Python), el toolbox ya está construido y no consulta el registro otra vez.

## Qué implica para este proyecto

- Compilar **una biblioteca por versión de Krita**:
  - K5: Qt 5.15.7, KF5, `libkritaui.so.20`
  - K6: Qt 6.8.0, KF6, `libkritaui.so.21`
- Cabeceras: árbol de fuentes de Krita 5.3.x y 6.0.0-beta1 (públicas y privadas:
  `KoToolManager_p.h`), más cabeceras de KF5/KF6.
- Enlazado contra las librerías de las AppImage extraídas (sin tocar la
  instalación), con `RPATH=$ORIGIN`.
- La herramienta nativa es **fina**: captura los eventos del lienzo, dibuja el
  trazo y avisa al docker; el cálculo sigue en el motor Rust.

## Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| ABI distinta entre Qt 6.8 (Krita) y Qt 6.10 (sistema) | Usar Qt 6.8.0 propio para el shim |
| Cabeceras privadas cambian entre versiones | Un shim por versión, con `#if` solo donde haga falta |
| KF5/KF6 no instalados | Cabeceras extraídas en `.deps/` (fuera de Git) |
| El plugin nativo rompe al cargar | Carga protegida: si falla, el docker arranca y avisa |

## Plan de validación de M3

1. Compilar el shim mínimo (una factoría + herramienta vacía) para Krita 6.
2. Cargarlo desde el plugin Python; comprobar en el log que la acción se inyecta
   y que el botón aparece en el toolbox (captura de pantalla).
3. Repetir con Krita 5.
4. Solo entonces añadir el dibujo de trazos.

Si el shim no se estabiliza en el tiempo de M3, se activa el plan B (D-004).
