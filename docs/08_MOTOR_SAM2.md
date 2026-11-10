# Motor SAM 2.1 (GPU)

## Por qué

MobileSAM (versión alpha) reconoce menos de lo que se espera de un roto brush:
necesita varios trazos y falla con objetos parecidos al fondo. SAM 2.1 es un
modelo mucho más capaz para segmentar objetos a partir de puntos y cajas.

## Arquitectura

```
Krita (plugin Python)
  └─ sam2_client.py  ── TCP 127.0.0.1:8765 ──►  engine/worker.py
                                                   └─ SAM 2.1 (PyTorch, GPU)
```

- El plugin manda la capa (RGBA/BGRA), los puntos de los trazos (verde=1,
  rojo=0) y una caja calculada con la extensión de los trazos verdes.
- El worker devuelve el alfa del mejor de los tres candidatos de SAM 2.1.
- Si el worker no responde, el plugin usa MobileSAM y lo avisa en el estado.

## Requisitos

- Python 3.12 con PyTorch CUDA en `.engine/venv` (no toca el Python de Krita).
- `sam2` (Apache-2.0) y el checkpoint `sam2.1_hiera_large.pt` en `.engine/models/`.
- GPU NVIDIA; sin ella funciona en CPU, mucho más lento.

## Puesta en marcha

1. Instalar el plugin: `bash scripts/install.sh` (deja la ruta del proyecto en
   `engine_dir` para que el plugin encuentre el motor).
2. Arrancar el motor: botón **“Arrancar motor SAM 2.1”** del docker, o a mano:
   `.engine/venv/bin/python engine/worker.py`.
3. En el docker, motor **SAM 2.1 (GPU)**; si no responde, cae a MobileSAM.

## Protocolo

4 bytes de longitud + JSON: `{"cmd":"segment","w","h","bgra","image","points","box"}`
→ `{"ok":true,"alpha","score","ms"}`. `{"cmd":"ping"}` para comprobar.

## Licencias

- SAM 2.1: Apache-2.0 (código y pesos, Meta AI).
- PyTorch: BSD-3-Clause.
- El plugin sigue siendo GPL-3.0-or-later; el worker es un proceso separado.
