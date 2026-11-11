# Decisiones

Formato corto: decisión, motivo, estado.

## D-001 — Motor basado en los crates de EffectCraft

Usar `effectcraft-track` / `effectcraft-segment` / `effectcraft-raster` 0.9.2
(crates.io, MIT OR Apache-2.0) en lugar de reimplementar SAM.
Es el mismo código que da la calidad del Roto Brush de EffectCraft, en Rust puro
(rayon), sin PyTorch. **Aceptada.**

## D-002 — Núcleo nativo, no Python puro

Krita 5 y 6 traen Python 3.13 **sin numpy** y no admiten instalar paquetes.
Todo el cálculo va en una biblioteca Rust (cdylib) llamada por `ctypes`.
**Aceptada.**

## D-003 — Herramienta en el toolbox vía shim nativo

Krita no permite registrar herramientas desde Python (`krita.pyi` no expone
ninguna clase de herramienta). Se replica el mecanismo de `krita-vision-tools`:
biblioteca C++ cargada con `ctypes` que registra la factoría en
`KoToolRegistry` y la inyecta en `KoToolManager`. Una compilación por versión de
Krita. **Aceptada** (con plan B en D-004).

## D-004 — Plan B si el shim no se estabiliza

Botón inyectado en la caja de herramientas desde Python + captura de eventos del
lienzo. Un solo código para Krita 5 y 6, sin ABI nativa. Se activa solo si D-003
falla en las pruebas de M3. **Aceptada como respaldo.**

## D-005 — Resultado en la capa original

Se lee la capa, se calcula el alfa y se escribe con `Node.setPixelData` en la
misma capa. Sin capas de preview ni de resultado. **Aceptada.**

## D-006 — Copia de seguridad para deshacer

La API Python no ofrece transacciones de deshacer para `setPixelData`. Antes de
aplicar se guarda en memoria el RGBA original y se ofrece “Restaurar”. La copia
no se escribe en disco. **Aceptada.**

## D-007 — Modelo fuera del repositorio

`mobile_sam.pt` se busca en una ruta configurable (variable de entorno y ajuste
del docker). Nunca se versiona ni se redistribuye. **Aceptada.**

## D-008 — Solo imagen fija

Sin vídeo ni tracking temporal en la v1. El motor lo soporta, pero multiplica
la complejidad de UI y pruebas. **Aceptada.**

## D-009 — Licencia GPL-3.0-or-later

El shim nativo enlaza con librerías de Krita (GPL) y se carga en su proceso.
Los crates de EffectCraft siguen siendo MIT/Apache-2.0. **Aceptada.**

## D-010 — Documentación corta y fragmentada

Cada documento y cada archivo de código, pequeño. Facilita revisión,
compactación de contexto y trabajo por etapas. **Aceptada.**

## D-011 — Graph cut + prior de MobileSAM por defecto

Motor `model` por defecto: el graph cut con la probabilidad de MobileSAM como
prior recupera zonas donde el color solo falla (pelo verde sobre fondo verde).
El motor `classic` queda como alternativa y `sam` solo para diagnóstico.
**Aceptada** tras las pruebas de M1 (`tests/results/README.md`).

## D-012 — Un trazo del pincel = un `Stroke` independiente

No se encadenan puntos de zonas distintas en una polilínea: la banda que los
une se pinta y rompe el resultado. **Aceptada** (fallo observado en M1).

## D-013 — Vista previa automática al soltar el trazo

Cada trazo dispara un recálculo (con 700 ms de espera para agrupar trazos
seguidos) y el alfa se escribe en la capa, de modo que el usuario ve el
resultado mientras sigue pintando. Se puede desactivar en el docker.
**Aceptada.**

## D-014 — El undo real exige el shim nativo

Comprobado en el código de Krita 6 (`libs/libkis/Selection.cpp`): las
operaciones de escritura de píxeles desde Python no crean pasos de deshacer.
Hasta que exista la herramienta nativa (M3), la herramienta ofrece **Restaurar**
y se evita ensuciar el undo cambiando a Move y consumiendo los eventos.
**Aceptada** como limitación temporal.

**Pendiente**: además, Ctrl-Z no funciona ni siquiera cuando el plugin está
inactivo; hay que restablecer el deshacer/deseleccionar nativo de Krita.

## D-016 — Versión alpha cerrada y salto a SAM 2.1

La versión con MobileSAM se cierra como **v0.1-alpha** (etiqueta `v0.1-alpha`).
El siguiente motor es **SAM 2.1** (Hiera-Large, Apache-2.0) ejecutado en un
**proceso aparte** con su propio Python y PyTorch (GPU), hablando por TCP local
con el plugin. Motivo: MobileSAM se queda corto en objetos parecidos al fondo y
en número de trazos necesarios; separar el motor evita meter PyTorch en Krita.
**Aceptada.**

## D-017 — SAM 3 queda en evaluación

SAM 3 (Meta, noviembre de 2025) añade *prompts por concepto* (texto), lo que
podría permitir “segmenta los cilindros”. Se evaluará después de estabilizar
SAM 2.1, porque exige otro repositorio y checkpoints y aún no hay integración
probada con este flujo.
