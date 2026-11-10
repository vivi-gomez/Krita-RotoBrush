# Plugin de Krita (Python)

`roto_brush/` es el paquete; `roto_brush.desktop` va **al lado**, no dentro.

## Piezas previstas

| Archivo | Responsabilidad |
|---|---|
| `__init__.py` | Registro del docker y carga de la herramienta |
| `loader.py` | `ctypes` de la herramienta nativa y del motor |
| `docker.py` | Panel de ajustes |
| `controller.py` | Trazos, recálculo, aplicar/restaurar |
| `canvas.py` | Coordenadas y captura de eventos |
| `logging.py` | Log propio, sin datos personales |

## Reglas

- Compatible PyQt5 (Krita 5) y PyQt6 (Krita 6): nada de alias planos de enums.
- Ningún cálculo pesado en el hilo de UI.
- Ninguna ruta absoluta de usuario en el código.
