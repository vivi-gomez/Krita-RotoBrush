# Diario

Registro de trabajo. Se añade al final; no se reescribe lo anterior.

## 2026-11-08 — Sesión 1: preparación del proyecto

**Objetivo:** dejar listo el proyecto (documentos, estructura, librerías y
modelos) antes de escribir código.

**Hecho**

- Auditoría del equipo: versiones de Krita, Python, Qt, Rust y modelos.
- Análisis del mecanismo de `krita-vision-tools` para poner herramientas en el
  toolbox (ver `docs/06_TOOLBOX_NATIVO.md`).
- Documentos `README`, `docs/01`–`07`, `ATTRIBUTION`, `.gitignore` y estructura
  de carpetas.
- Inventario de modelos con SHA-256 y licencias.

**Hallazgos**

- Krita 5.3.x y Krita 6 beta1 usan **Python 3.13**, y **ninguna trae numpy**:
  el cálculo tiene que ir en un núcleo nativo.
- La API Python de Krita no permite registrar herramientas; hay que usar un shim
  C++ cargado con `ctypes`, como Acly.
- Los crates `effectcraft-*` 0.9.2 están publicados en crates.io y ya incluyen
  trazos FG/BG/Refine, graph-cut con prior de MobileSAM y el matte de Refine
  Edge (pelo). Es el camino corto a la calidad de EffectCraft.
- Krita 6 trae Qt 6.8.0; el sistema tiene 6.10.2. Para el shim habrá que usar
  Qt 6.8.0 propio.

**Pruebas**

| Prueba | Resultado |
|---|---|
| Escritura en la carpeta del proyecto (intento 1) | **Falló**: solo lectura + permiso denegado |
| Escritura (intento 2, tras cambiar la política) | **OK** (archivo creado y borrado) |
| Lectura de AppImages (versiones, PyQt, libs) | OK |
| SHA-256 de modelos e imagen de prueba | OK |

**Lección del intento anterior** (proyecto viejo, 2026-11-07): la máscara salió
en bloques y se crearon capas auxiliares que ensuciaban el documento. De ahí
D-005 (misma capa) y la exigencia de validación visual en N4.

**Pendiente**

- M1: motor Rust + CLI de prueba sobre `assets/`.
- Confirmar la ruta del modelo en el docker.

## 2026-11-08 — Sesión 1: hito M1 (motor)

**Objetivo:** motor Rust + CLI que saque el alfa sobre la imagen de prueba.

**Hecho**

- Workspace `core/` con `roto_brush_core` (cdylib + rlib) y `roto_cli`.
- Dependencias fijadas a `effectcraft-track`/`segment`/`raster` 0.9.2 (crates.io).
- API: `render_alpha`, `render_rgba`, `image_from_rgba`, `Model::from_file`.
- Tres motores: `classic` (color), `model` (graph cut + prior MobileSAM) y
  `sam` (probabilidad del modelo tal cual), elegibles con `--engine`.
- 4 pruebas unitarias: **4/4 OK**.

**Pruebas**

| Prueba | Resultado |
|---|---|
| Compilar workspace | OK (aviso: la firma de `decontaminate` en 0.9.2 no es la del repo v0.21.1) |
| Segmentación con 1 polilínea | **Mala** (huecos en diagonal) |
| Segmentación con trazos separados, classic | Aceptable (restos de fondo) |
| Segmentación con trazos separados, model | **Buena** (cuernos, patas, libro) |
| Refine Edge en el pelo | Actúa, pero deja halo con `smooth 2` |
| Tiempos CPU | 0.5–2.5 s por imagen de 1024² |

**Notas**

- El motor publicado en crates.io (0.9.2) difiere del árbol v0.21.1 del
  repositorio de EffectCraft: firmas y módulos cambian (`roto/mod.rs` vs
  `roto.rs`). Hay que atenerse al código del crate descargado, no a `vendor/`.
- Las imágenes de resultado están en `tests/results/` (ignoradas por git).

**Pendiente**

- Ajustar valores por defecto de Refine Edge (halo) y de descontaminación.
- M2: API C estable y prueba desde Python 3.13.

## 2026-11-08 — Sesión 1: prueba manual en Krita (instalación)

**Objetivo:** instalar una primera versión para que el usuario la pruebe.

**Hecho**

- API C estable en el motor (`rb_model_load`, `rb_render`, `rb_model_free`,
  `rb_version`) y **probada desde ctypes** con una imagen sintética.
- Plugin Python con docker: modos FG/BG/Refine, tamaño de pincel, Feather,
  Smooth, Mejor calidad, Descontaminar, Aplicar, Restaurar, Borrar trazos.
- Captura de trazos con filtro a nivel de aplicación, limitada al lienzo y con
  exclusión de diálogos modales; overlay transparente (verde/rojo/azul).
- Cálculo en hilo aparte; la escritura se hace en el hilo de UI sobre la capa
  activa (`setPixelData`) con copia en memoria para **Restaurar**.
- Instalado en el perfil: `~/.local/share/krita/pykrita/roto_brush/` y
  `enable_roto_brush=true` en `kritarc` (con copia de seguridad previa).

**Pruebas**

| Prueba | Resultado |
|---|---|
| FFI desde ctypes (64×64 sintética) | OK (alfa medio 127,5) |
| Harness de importación con PyQt6 | **5/5 PASS** |
| Harness de importación con PyQt5 | **5/5 PASS** |
| Arrancar Krita 6 extraída, 1.er intento | **Falló**: *Failed to import encodings* (AppImage extraída sin `PYTHONHOME`) |
| Arrancar Krita 6, 2.º intento | **Falló**: la pantalla `:0` dejó de responder a mitad de la prueba |

No se pudo comprobar el plugin dentro de Krita: la sesión gráfica se perdió.
Queda pendiente la validación visual del usuario.

**Nota de privacidad**

La primera captura fue de todo el escritorio y mostraba ventanas personales; se
borró. A partir de ahora solo se captura la ventana de Krita por su id.

**Pendiente**

- Confirmar que el docker aparece en Krita 5 y 6.
- Afinar valores por defecto (el resultado aún no llega al de EffectCraft).
- M3: herramienta en el toolbox.

## 2026-11-08 — Sesión 1: feedback del usuario (ronda 1)

**Fallos reportados** (idénticos en Krita 5 y 6)

1. Al activar el pincel desaparece el cursor y no se ve el trazo.
2. El contador de trazos sube, así que la captura sí funciona.
3. Faltaba el concepto de máscara que se regenera al pintar.
4. Tras aplicar no debería hacer falta desactivar la herramienta.
5. Ctrl+Z no deshace la herramienta (deshacía trazos anteriores).

**Causas y correcciones**

- El overlay se creaba pero **nunca se mostraba** (`show()` no se llamaba en un
  hijo creado después del padre): de ahí que no se viera nada. Ahora se muestra,
  se sincroniza y pinta el **círculo del pincel** con el tamaño real.
- El cursor del lienzo se ocultaba al taparlo el overlay; ahora el overlay usa
  cursor en blanco y dibuja su propio círculo (el usuario siempre ve dónde pinta).
- Se activa `mouseTracking` mientras dura la captura para poder dibujar el
  círculo sin pulsar.
- Se cambia la herramienta activa a **Move** al activar y se restaura al salir:
  así el pincel normal no pinta ni ensucia el undo.
- **Vista previa automática**: al soltar el trazo se recalcula (700 ms de
  espera) y el alfa se escribe en la capa. Se puede desactivar con la casilla.
- El origen de la imagen se guarda una sola vez, así que recalcular no acumula
  transparencia.
- "Aplicar" pasa a "Recalcular"; el resultado ya está en la capa.

**Undo (pendiente, requiere nativo)**

Verificado en el código de Krita 6 (`libs/libkis/Selection.cpp`):
`Selection::cut` y `setPixelData` escriben directamente en el dispositivo, sin
comando de deshacer. La API Python **no puede** crear pasos de undo. Hace falta
el shim nativo (M3) para envolver la escritura en un `KUndo2Command`.

**Pruebas**

| Prueba | Resultado |
|---|---|
| Harness PyQt6 | 6/6 PASS |
| Harness PyQt5 | 6/6 PASS |
| Validación visual en Krita | Pendiente (sin pantalla disponible) |

**Versiones**

crates.io solo publica `effectcraft-*` 0.9.2 (4-nov-2026); la app 0.22 usa su
propio versionado de workspace. No hay salto de versión que explique la calidad.

## 2026-11-08 — Sesión 1: error de `RoundCap` en Qt6

**Síntoma**: al primer clic, ventana "script error":
`AttributeError: type object 'PenStyle' has no attribute 'RoundCap'`.

**Causa**: en Qt6 los extremos de pluma viven en `Qt.PenCapStyle` y las uniones
en `Qt.PenJoinStyle`; mi helper `pen_style()` los buscaba en `Qt.PenStyle`.

**Corrección**: helpers separados `cap_style()` y `join_style()` y uso correcto
en el overlay. Además `paintEvent` ahora captura cualquier excepción y la anota
en el log, para que un fallo de dibujo no abra un diálogo modal.

**Prueba nueva**: el arnés dibuja el overlay de verdad (`overlay.grab()`) con
una vista simulada, así se cubre el camino de los `QPen`.

| Prueba | Resultado |
|---|---|
| Harness PyQt6 (7 comprobaciones) | 7/7 PASS |
| Harness PyQt5 (7 comprobaciones) | 7/7 PASS |
| Instalación en el perfil | OK |

## 2026-11-08 — Sesión 1: máscaras absurdas y trazos viejos (ronda 2)

**Síntomas del usuario (Krita 6)**

1. Verde: borra el personaje y deja el fondo. Rojo: borra todo. Azul: nada.
2. Da igual dónde pinte: el resultado no depende del trazo.
3. Al cerrar y reabrir la imagen, al reactivar aparecen los trazos anteriores.

**Causa raíz (1 y 2)**

`flakeToCanvasTransform()` y `flakeToImageTransform()` son métodos de **View**,
no de **Canvas**. Mi código los llamaba sobre `view.canvas()`, lanzaba
`AttributeError` (que quedaba en el log) y caía al retorno de emergencia:
coordenadas de widget (p. ej. 1578, 562) sobre una imagen de 1024. Los trazos
quedaban fuera de la imagen, no había restricciones duras y la máscara salía
arbitraria e idéntica hiciera lo que hiciera el usuario.

Comprobado en el código de Krita 6 (`libs/libkis/View.cpp`):
- `flakeToCanvasTransform` = flake → widget.
- `flakeToImageTransform` = image → flake invertido (flake → imagen).

Corregido: widget → flake (inversa) → imagen. El test del arnés usa una
transformación con escala 2 y desplazamiento para comprobar ida y vuelta.

**Causa (3)**: los trazos vivían en el controlador y no se limpiaban al cambiar
de documento. Ahora `_sync_document()` borra trazos y origen al detectar otro
documento.

**Extras**

- Si ningún punto del trazo cae dentro de la capa, se avisa y no se calcula.
- El log anota el primer punto en coordenadas de imagen y el % de primer plano
  de cada vista previa.

| Prueba | Resultado |
|---|---|
| Arnés PyQt6 (8 comprobaciones) | 8/8 PASS |
| Arnés PyQt5 (8 comprobaciones) | 8/8 PASS |
| Validación visual | Pendiente del usuario |

## 2026-11-08 — Sesión 1: coordenadas reales, BGRA y zoom (ronda 3)

Con Krita 6 arrancada desde la AppImage extraída (con `PYTHONHOME`) ya se puede
diagnosticar sin depender del usuario. Añadí dos modos por variable de entorno:
`ROTO_BRUSH_DUMP` (vuelca widgets y transformaciones) y `ROTO_BRUSH_SELFTEST`
(segmenta la capa activa con trazos fijos y guarda un PNG).

**Hallazgos**

1. `View` tiene `flakeToCanvasTransform` (flake→widget) y
   `flakeToImageTransform` (flake→imagen con escala 1/zoom). Comprobado con
   documento de 1024, zoom 1,8896: `flake->canvas` = traslación (519, 0),
   `flake->imagen` = escala 0,529. La composición widget→flake→imagen da el
   centro del lienzo como (511,2, 511,7): correcto.
2. El widget que usa ese espacio es el **hijo del viewport con su misma
   geometría** (2972x1935), no el QMdiArea ni el QMdiSubWindow. Ahora se elige el
   más profundo del árbol; con eso el overlay se cuelga del lienzo real y se ve.
3. **Krita entrega los píxeles en BGRA**, no RGBA: primer píxel de la capa
   `[129, 195, 182]` frente a `(182, 195, 129)` del PNG. El motor recibía rojo y
   azul cambiados y segmentaba mal. Añadido `bgra` a la API C (se convierte en
   Rust, sin coste en Python).
4. Autoprueba dentro de Krita con 3 trazos cortos: máscara coherente (cara,
   libro y un pie; 19,5 % de primer plano). Antes del arreglo de BGRA salía
   ruido.
5. **Zoom y otras herramientas**: el filtro consumía todos los clics. Ahora solo
   captura con el **botón izquierdo** y mientras la herramienta activa sea la
   neutra (Move); si el usuario elige Zoom o Pan, los eventos pasan a Krita.

**Nota**: los "trazos" son polilíneas; encadenar dos zonas lejanas pinta una
banda entre ellas. En la autoprueba eso generó bandas diagonales al usar los
cuatro píxeles de las esquinas como un solo trazo de fondo.

| Prueba | Resultado |
|---|---|
| Autoprueba dentro de Krita 6 (BGRA corregido) | Máscara coherente |
| Arnés PyQt5/PyQt6 | 8/8 y 8/8 |
| Widget elegido | QWidget 2972x1935, centro→imagen (511,2, 511,7) |

## 2026-11-08 — Sesión 1: identidad de envoltorios de Krita (ronda 4)

**Síntoma**: "los trazos están fuera de la imagen" y, en Krita 5,
`IndexError: list index out of range` en `compute`.

**Causa raíz**: Krita devuelve un **envoltorio Python nuevo** cada vez que se
pide `activeDocument()`, `activeNode()` o `rootNode()`. Yo comparaba con `is`:

- `_sync_document()` creía siempre que el documento había cambiado → borraba los
  trazos justo al calcular → el aviso de "fuera de la imagen" y el IndexError.
- `self.source[0] is not node` era siempre cierto → se releía la capa ya
  previsualizada en cada cálculo → **el alfa se multiplicaba una y otra vez**
  (de ahí que "desapareciera todo").

**Corrección**: identidad estable con `uniqueId()` del nodo raíz (documento) y
del nodo (capa). El origen se captura una sola vez; `Restaurar` usa el nodo
guardado si su id coincide.

**Verificación dentro de Krita 6** (clic simulado en el centro del lienzo):
- `primer trazo en imagen: (511.2, 511.7)`
- `motor: 1024x1024 en 1.85 s`
- `aplicado: primer plano 46.5 %` (el yeti ocupa justo eso)

**Diagnóstico añadido**
- `~/.local/share/krita/roto_brush_boot.log`: registro mínimo de arranque con
  traza si el plugin no carga.
- `ROTO_BRUSH_DUMP`, `ROTO_BRUSH_SELFTEST`, `ROTO_BRUSH_EVENTTEST`,
  `ROTO_BRUSH_ZOOM`: pruebas automáticas por variable de entorno.

## 2026-11-08 — Sesión 1: vista previa no destructiva (ronda 5)

**Síntomas**: pintar verde ya aplicaba transparencia y la imagen desaparecía; no
se podía seguir pintando; rojo o Refine sin primer plano borraban todo;
Restaurar no limpiaba los trazos.

**Correcciones**

1. **La vista previa ya no toca la capa.** El cálculo guarda la máscara y el
   overlay atenúa el fondo (nuevo `rb_dim_mask` en el motor). La capa solo se
   modifica al pulsar **Aplicar**.
2. **Se exige al menos un trazo de primer plano** para calcular. Con solo fondo
   o solo Refine no se calcula ni se aplica nada (antes la máscara vacía dejaba
   todo transparente).
3. **Restaurar** devuelve la capa, borra la máscara y **limpia los trazos**.
4. **El área de la capa se fija al primer cálculo.** Tras aplicar, `node.bounds()`
   se encoge (Krita recalcula el rectángulo con contenido) y recalcular con esa
   área desalineaba la máscara. Ahora se reutiliza el rectángulo original.

**Verificación dentro de Krita 6**: clic simulado → máscara 1024×1024 al 46,5 %
sin escribir en la capa; al pulsar Aplicar → `aplicado: primer plano 46.5 %`.

**Nota**: el docker se puede crear dos veces si se abre el panel y además hay una
prueba automática activa; solo afecta a las pruebas.

## 2026-11-08 — Sesión 1: máscara desplazada y trazos que estorban (ronda 6)

**Síntoma**: la vista previa se dibujaba desplazada (el fondo atenuado no coincidía
con el objeto) y los trazos se quedaban encima, tapando la imagen.

**Causa del desplazamiento**: orden de multiplicación de `QTransform`. Qt aplica
en el orden escrito (`p * A * B` = A y luego B), así que imagen→widget es
`inv(flakeToImage) * flakeToCanvas`; yo tenía los factores al revés. Con los
datos reales (zoom 1,8896, dx=519) el error sumaba ~981 px de desplazamiento.

**Corrección**: `image_transform()` devuelve `inv(to_image) * to_canvas`. Ahora
imagen(0,0)→(519, 0) e imagen(512,512)→(1486,5, 967,5), que coincide con el
centro del lienzo (1485, 967). Añadida prueba en el arnés con transformaciones
de escala distinta para que un error de orden no vuelva a pasar.

**Trazos**: se ocultan en cuanto la máscara está calculada; solo se ve el trazo
que se está pintando. `computed_strokes` guarda cuántos están ya procesados.

| Prueba | Resultado |
|---|---|
| Arnés PyQt5/PyQt6 (9 comprobaciones) | 9/9 y 9/9 |
| Transformación de la máscara con datos reales | coincide con el centro del lienzo |
| Ciclo completo en Krita 6 | máscara 46,5 % y Aplicar correcto |

## 2026-11-08 — Sesión 1: calidad de vista previa y cambio de imagen (ronda 7)

**Feedback**: trazos que sobreviven al cambiar de imagen; bordes dentados; la
vista previa no permite juzgar el resultado; el botón sigue activo con la imagen
nueva; rojo sin verde no hace nada.

**Cambios**

1. **Vista previa suave**: la atenuación ahora es proporcional al alfa
   (`rb_dim_mask` calcula `(255-alfa)*factor`), así que los bordes suaves se ven
   suaves en pantalla y no como un recorte dentado.
2. **Feather por defecto a 1,0 px** (antes 0), para que el matte final no salga
   con escalones. El control sigue en el docker.
3. **Vigilante de documento**: un temporizador cada 700 ms detecta el cambio de
   documento por `uniqueId` del nodo raíz, limpia trazos y máscara, y **rearma**
   la captura con el lienzo de la imagen nueva. El estado del botón se
   sincroniza con una señal (`armed`), sin bucles de `setChecked`.
4. **Peso del modelo configurable** en el motor (`sam_weight`, por defecto 6):
   permite que MobileSAM pese más que el color si hace falta. Probado en el CLI
   con 4/6/10/20: el resultado cambia poco en la imagen de prueba (45,5 % → 42,9 %),
   así que el color sigue mandando; queda como palanca para fotos difíciles.

**Por diseño**: el trazo rojo solo corrige una máscara existente; sin un trazo
verde previo no hay nada que corregir y no se calcula.

**Pruebas**

| Prueba | Resultado |
|---|---|
| Arnés PyQt5/PyQt6 | 9/9 y 9/9 |
| Pesos SAM en el CLI | poca variación (42,9–45,5 %) |
| Verificación en Krita | **no completada**: el proceso no pudo crear los archivos de log en esta sesión |

## 2026-11-08 — Sesión 1: controles de propagación y suavizado (ronda 8)

**Feedback**: hace lo que promete pero con mala calidad; faltan controles de
propagación como en EffectCraft; verde y rojo se autopropagan a otras zonas;
el Refine sale pixelado.

**Cambios**

1. **Docker con más control**: Feather, Smooth, **Contraste**, **Desplazar
   borde**, **Peso del modelo** (MobileSAM vs color), **Radio de búsqueda**,
   **Limpiar islas**, Mejor calidad y Descontaminar.
2. **Limpieza de islas** en el motor: elimina componentes conexas de primer
   plano menores de ~0,08 % de la imagen. Ataca las fugas del graph cut.
3. **Radio de búsqueda** conectado a `SegOpts.search_radius` (antes fijo en 15).
4. **Vista previa suave también al ampliar**: añadido
   `SmoothPixmapTransform`; el aspecto "pixelado" del Refine era en parte el
   escalado de la imagen de máscara sin interpolación.
5. Feather por defecto 1,0 px ya activo.

**Pruebas**

| Prueba | Resultado |
|---|---|
| CLI con feather 1,0 y limpieza | 45,0 % de primer plano, bordes suaves |
| Arnés PyQt5/PyQt6 | 9/9 y 9/9 |

## 2026-11-08 — Sesión 1: edición de trazos y vista de máscara (ronda 9)

**Pedido**: poder retocar trazos ya pintados sin borrarlos; ver solo la máscara.

**Hecho**

1. **Trazos finos**: el overlay dibuja ahora una línea por trazo (2 px) en vez de
   la banda del pincel, para no tapar la imagen.
2. **Selección de trazos**: con "Editar trazos" activo, un clic selecciona el
   trazo más cercano (≤14 px de imagen) y lo resalta en blanco. El control de
   tamaño cambia el pincel de ese trazo y "Borrar seleccionado" lo elimina.
3. **Ver solo la máscara**: nuevo `rb_gray_mask` en el motor y casilla en el
   docker; pinta blanco/negro con grises para el feather, sin la imagen.
4. El overlay solo muestra los trazos que se están pintando (o todos en modo
   edición), así el resultado queda limpio.

**SAM 2.1**: `effectcraft-sam2` **no está publicado en crates.io**; vive en el
repositorio de la app, depende de `candle-core`/`candle-nn` 0.9.2 y no implementa
`MaskModel` (tiene su propia API `ImageModel::open/encode/segment`). Requeriría
vendorizar el crate, compilar candle y un camino nuevo en el motor. Con
Hiera-Large (224 M parámetros) en CPU sería muy lento para edición interactiva.
Queda como modo opcional "máxima calidad" para equipos con GPU.

| Prueba | Resultado |
|---|---|
| Arnés PyQt5/PyQt6 (11 comprobaciones) | 11/11 y 11/11 |
| Máscara gris y atenuada (unitaria) | OK |
| Edición de trazos (unitaria) | OK |

## 2026-11-08 — Sesión 1: memoria tras aplicar, edición y dibujos de línea (ronda 10)

**Pedido**: liberar la memoria de trazos al aplicar (y al cambiar de imagen),
que los ajustes afecten al trazo seleccionado, y manejar dibujos de líneas.

**Hecho**

1. **Aplicar limpia la herramienta**: tras escribir la transparencia se vacían
   trazos, máscara y selección. El vigilante de documento sigue limpiando al
   abrir otra imagen.
2. **La edición ya no pinta**: con "Editar trazos" activo, los movimientos del
   pincel no añaden puntos al último trazo (antes lo alargaban por accidente).
3. **Ajustes en vivo**: mover Feather, Smooth, Contraste, Desplazar borde, Peso
   del modelo, Radio de búsqueda, Limpiar islas o Rellenar contornos recalcula
   la máscara automáticamente si ya hay una.
4. **Rellenar contornos** (nuevo en el motor): rellena los huecos cerrados que no
   se alcanzan desde el borde, para que un dibujo de líneas quede como
   contorno + relleno. Se puede desactivar.
5. CLI: opciones `--no-fill` y `--no-clean` para comparar.

**Prueba sintética de línea**: círculo negro sobre blanco, 512×512, un trazo
dentro → 32,1 % de primer plano, idéntico con y sin relleno (el graph cut ya
cogía el interior). La opción queda para los casos en que el interior se pierde.

**GPU**: el usuario confirma que la NVIDIA ya está operativa; SAM 2.1 pasa a ser
viable, pero sigue sin publicarse `effectcraft-sam2` (requiere vendorizar candle).
Se propone como siguiente bloque tras la herramienta del toolbox y el undo.

## 2026-11-08 — Sesión 1: botón, ajustes y persistencia (ronda 11)

**Síntomas**: el botón aparece activo sin pulsarlo; cambiar ajustes no parece
afectar al trazo seleccionado; los trazos sobreviven al cerrar imágenes.

**Cambios**

1. **Notifier de Krita**: el controlador se conecta a `imageCreated`,
   `imageClosed`, `viewCreated`, `viewClosed` y `windowCreated`. Al abrir o cerrar
   una imagen se vacían trazos, máscara y selección, y la captura se rearma sola
   si estaba activa. Es más fiable que el temporizador, que se mantiene como
   respaldo.
2. **El botón ya no se marca solo**: eliminada la emisión `armed(True)`; solo el
   clic del usuario activa la captura, y `armed(False)` se usa únicamente si la
   captura falla.
3. **Ajustes ligados al trazo seleccionado**: además del tamaño, se puede cambiar
   su tipo con "→ verde", "→ rojo", "→ refine". El estado muestra índice, tipo y
   pincel del trazo elegido.
4. **Todos los ajustes recalculan**: tamaño, mejor calidad, descontaminar, radio
   de búsqueda, contornos e islas incluidos.

**Pendiente**: confirmar en Krita que el notifier dispara en Krita 5 y 6 (no hay
verificación visual disponible en esta sesión).

## 2026-11-08 — Sesión 1: feather por trazo (ronda 12)

**Pedido**: poder dar a un trazo concreto un feather distinto (pelo frente a
ropa), sin rehacer los demás.

**Hecho**

- El motor acepta ahora `StrokeSpec { stroke, feather }`: feather propio por
  trazo (-1 = usa el global).
- `local_feather` en Rust: para cada trazo con feather propio, rasteriza su
  banda, calcula una caída gaussiana normalizada (influencia = radio·3 +
  feather·4) y mezcla el alfa con una versión desenfocada **solo en esa zona**.
  Así el borde cercano a ese trazo se suaviza y el resto no cambia.
- API C actualizada: cada trazo viaja como `[kind, radius, feather, n, x, y…]`.
- Docker: control **Feather del trazo** (0 = heredar) que actúa sobre el trazo
  seleccionado; el estado muestra el feather propio del trazo elegido.
- CLI: `--stroke-feather N` para comparar.

**Pruebas**

| Prueba | Resultado |
|---|---|
| CLI con y sin feather por trazo | salidas distintas (PNG distinto) |
| Arnés PyQt5/PyQt6 | 11/11 y 11/11 |
| Media de alfa | cambia muy poco: el efecto es local, como se pretende |

**Futuro anotado**: profundidad (Marigold) para refinar bordes y separar planos;
SAM 2.1 con GPU; herramienta en el toolbox y undo nativo.

## 2026-11-08 — Sesión 1: error al primer trazo (ronda 13)

**Síntoma**: `ValueError: too many values to unpack (expected 3)` en
`_strokes_inside` al primer trazo.

**Causa**: al añadir el feather por trazo, los trazos pasaron de 3 a 4 campos
(`tipo, radio, puntos, feather`) y quedó un desempaquetado antiguo en la
comprobación de límites.

**Corrección**: desempaquetado a 4 campos y **prueba en el arnés** que llama a
`_strokes_inside` con trazos reales, para que este tipo de olvido falle en el
arnés y no en Krita. Arnés: 11/11 en PyQt5 y PyQt6.

## 2026-11-08 — Sesión 1: overlay destruido y botón al abrir (ronda 14)

**Síntoma**: al abrir la imagen de nuevo, `RuntimeError: wrapped C/C++ object of
type Overlay has been deleted` en `_refresh`, y el botón "Activar pincel"
aparecía marcado.

**Causa**: al cerrar la imagen, Krita destruye el overlay (hijo del lienzo),
pero el controlador seguía guardando la referencia. Además, al abrir una imagen
se rearmaba la captura si estaba activa, dejando el botón marcado.

**Corrección**

- `overlay_update()` y `set_hover()` capturan `RuntimeError` y olvidan el
  overlay muerto; `_drop_overlay()` limpia la referencia antes de `deleteLater`.
- Al abrir o cerrar una imagen se **desactiva** la herramienta: se paran los
  temporizadores, se suelta la captura, se restaura la herramienta anterior y se
  emite `armed(False)`, así el botón queda desmarcado.
- Arnés: prueba con un overlay que lanza `RuntimeError`; 12/12 en PyQt5 y PyQt6.

## 2026-11-08 — Sesión 1: defaults, botones y contaminación (ronda 15)

**Pedido**: resetear ajustes al cerrar la imagen (o botón de valores por
defecto); quitar los botones "→ verde / → rojo / → refine"; que los ajustes no
sean globales y que un trazo nuevo no contamine lo que ya estaba bien.

**Hecho**

1. **Restablecer ajustes**: botón en el docker y `reset_params()` que vuelve a
   los valores de fábrica (pincel 18, feather 1,0, smooth 1,0, contraste 0,
   desplazamiento 0, búsqueda 15, peso 6, limpiar/rellenar/descontaminar/mejor
   calidad activos, modos y vistas apagados). Se ejecuta también al abrir o
   cerrar una imagen; los controles del docker se sincronizan con la señal
   `params_reset`.
2. **Botones de tipo eliminados**: "→ verde / → rojo / → refine" fuera. Para el
   tipo se usan los modos de la herramienta.
3. **Máscara anterior como punto de partida**: el motor acepta ahora la máscara
   del cálculo anterior y la mezcla con la del modelo (peso 2,0). Así un trazo
   nuevo corrige la zona que toca en vez de re-segmentar desde cero, que era lo
   que ensuciaba el pelo ya correcto.

**Pruebas**: arnés 13/13 con PyQt5 y PyQt6 (incluye "restablecer ajustes").

## 2026-11-08 — Sesión 1: TypeError al sincronizar controles (ronda 16)

**Síntoma**: al abrir Krita sin imagen,
`TypeError: setValue(self, val: int): argument 1 has unexpected type 'float'`
en `docker._sync_controls`.

**Causa**: `brush` es `float` en el controlador y `QSpinBox.setValue` exige `int`
en PyQt6.

**Corrección**: `setValue(int(round(v)))` para todos los controles, y la prueba
del arnés llama ahora a `_sync_controls()` directamente (las excepciones dentro
de un slot las traga PyQt y no hacían fallar el test).

## 2026-11-08 — Sesión 1: undo interno y atajos de herramientas (ronda 17)

**Pedido**: que Ctrl+Z deshaga la herramienta (trazos, ajustes y la aplicación) y
que los atajos de zoom/mano funcionen.

**Hecho**

1. **Pila de deshacer interna** en el controlador (60 pasos): se apila antes de
   cada cambio (trazo nuevo, tipo, feather, radio, borrar, limpiar, aplicar).
2. **Ctrl+Z interceptado** por el filtro de captura mientras la herramienta está
   activa: deshace el último paso. Si hay una aplicación hecha, el primer Ctrl+Z
   devuelve la capa a su estado original usando el búfer en memoria.
3. **Atajos de herramientas**: `tool_is_neutral()` ya no mira la acción guardada
   sino **cuál está marcada ahora** entre las acciones `tool_*`. Al cambiar a
   zoom, mano o cualquier otra, la captura deja pasar los eventos y el atajo
   funciona.

**Límites (documentados)**: esto no es el undo de Krita. Si se cierra el
documento o se desactiva la herramienta, Ctrl+Z vuelve al undo de Krita y no
recupera nuestro cambio. Para integrarlo de verdad hace falta el shim nativo
(`KUndo2Command`), la misma pieza que la herramienta del toolbox (M3).

| Prueba | Resultado |
|---|---|
| Arnés PyQt5/PyQt6 | 14/14 y 14/14 |
| Deshacer trazos (unitaria) | OK |

## 2026-11-09 — Sesión 2: teclas, tamaño, calidad, tamaño del .so y limpieza (ronda 18)

**Hallazgo importante en los logs**: `~/.local/share/krita/roto_brush.log` había
crecido a **215 MB** por un error repetido en cada repintado del overlay
(`ValueError: not enough values to unpack (expected 4, got 3)`, de la versión
anterior). Escribir ese volumen en disco explica gran parte de los tirones.
- Log truncado y añadida **rotación automática** a 1 MB (`roto_brush.old.log`).

**Hecho**

1. **Teclas**: Supr/Retroceso borra el trazo seleccionado; la barra espaciadora
   suspende la captura (desplazamiento normal); Ctrl+Z se instala como atajo
   propio mientras la herramienta está activa (se guardan y restauran los atajos
   de `edit_undo` de Krita).
2. **Tamaño de pincel solo para Refine**: FG/BG usan radio fijo de 8 px.
3. **Calidad de borde**: nuevo filtro guiado por color (`Suavizar borde`, 0–12,
   por defecto 4) que mezcla el alfa con una versión guiada por la imagen.
   Comprobado en el yeti: con 8 el borde queda limpio y sin dentado.
4. **`.so` más pequeño**: perfil release con LTO, `codegen-units=1` y
   `strip="symbols"`: de 1,94 MB a **1,02 MB**. Contiene el motor Rust
   (graph-cut, matte, MobileSAM) y sus dependencias (rayon, serde, effectcraft);
   no incluye modelos ni UI.
5. **controller.py dividido**: 870 → 262 líneas, con `edits.py` (187),
   `compute.py` (288) y `diagnostics.py` (151).
6. **Rendimiento**: `_refresh()` ya no recoloca el overlay en cada movimiento;
   solo repinta. El vigilante pasa a 1500 ms y la restauración de herramienta
   al cerrar imagen se difiere con `singleShot(0)`.

**Pendiente**: calidad del Refine en pelo (la zona de banda aún deja halos
grises); siguiente ronda.

## 2026-11-10 — Sesión 3: "no encuentra el lienzo" (ronda 19)

**Síntoma**: al pulsar "Activar pincel", el plugin no encuentra el lienzo.

**Cambios**

- `find_canvas_widget` acepta el widget del docker como respaldo para obtener la
  ventana, baja el umbral de área al 10 % y **registra** cuántas áreas de
  desplazamiento ve y qué candidato elige (o por qué no hay ninguno).
- `Controller.window` cae a `Krita.instance().windows()[0]` si no hay ventana
  activa.
- El docker avisa "abre una imagen antes de activar el pincel" cuando no hay
  documento, en vez del mensaje genérico.

## 2026-11-10 — Sesión 3: causa real de "no encuentra el lienzo" (ronda 20)

**Reproducido**: al partir `controller.py` en módulos se perdió el decorador
`@property` de `window`. `self.c.window` pasaba a ser un método y
`find_canvas_widget` recibía una función → `AttributeError: 'function' object has
no attribute 'qwindow'` → "sin ventana" → "captura: sin lienzo".

**Corrección**: decorador restaurado. Verificado en Krita 6 real (AppImage
extraída): clic simulado en el centro → `primer trazo en imagen: (511.7, 511.7)`,
`máscara 1024x1024 al 46,6 %`, `aplicado: 46.6 %`.

**Prueba añadida**: el arnés comprueba que `window`, `view` y `document` siguen
siendo propiedades. Arnés: 15/15 en PyQt5 y PyQt6.

## 2026-11-10 — Sesión 3: capa desplazada respecto al lienzo (ronda 21)

**Síntoma**: con una capa de tamaño distinto al lienzo, la máscara sale
desplazada (en `assets/prueba.kra`: documento 1024×1024, capa 2247×1481).

**Causa**: los trazos se guardan en coordenadas de **documento**, pero el motor
recibe los píxeles del **rectángulo de la capa**. Si la capa tiene origen
distinto de (0,0), había que restar ese origen y no se hacía: el motor
segmentaba como si la capa empezara en (0,0) y el resultado se escribía
desplazado.

**Corrección**: `_to_layer()` traslada cada punto por `-rect.x, -rect.y` antes de
llamar al motor (también en la autoprueba). Prueba en el arnés con rect
(50, 60): un punto (150, 110) pasa a (100, 50).

**Verificado en Krita 6** con `prueba.kra`: la autoprueba trabaja sobre la capa de
2247×1481 y guarda su PNG sin desplazamiento interno.

## 2026-11-10 — Sesión 3: calidad en la foto de cilindros (ronda 22)

Probado el motor con `assets/prueba.kra` (extraído `mergedimage.png`, 1024×1024)
sobre un cilindro del fondo:

| Prueba | Primer plano | Lectura |
|---|---|---|
| `classic` | 52,8 % | inútil: se come el pavimento |
| `model` (actual) | 2,7 % | el cilindro, casi completo |
| `sam` solo | 2,3 % | parecido, algo menos |
| clic suelto (1 punto) | 0,8 % | se queda corto |
| arrastre corto | 3,3 % | cilindro completo |

**Conclusiones**

- El motor sí reconoce el objeto; lo que falla es dar un **clic sin arrastre**
  (un punto apenas da información) y el suavizado por defecto, demasiado bajo.
- Un arrastre corto dentro del cilindro basta; el rojo ayuda pero no es
  imprescindible.

**Cambios**: Feather por defecto 1,5 (antes 1,0) y **Suavizar borde 8** (antes
4); el control llega a 16. Verificado con el cilindro: forma completa y borde
suave a 8–12.

**Pendiente**: pelo difuso (sigue siendo el punto débil) y valorar SAM 2.1 con
GPU.

## 2026-11-10 — Sesión 3: cierre de la alpha y motor SAM 2.1 (ronda 23)

**Hecho**

1. Versión alpha **cerrada**: commit `ee40ce0` y etiqueta `v0.1-alpha`.
2. **PyTorch 2.6 + CUDA 12.4** en `.engine/venv` (fuera de Krita) y `sam2`
   (Apache-2.0) con `sam2.1_hiera_large.pt` (898 MB) en `.engine/models/`.
3. **Prototipo SAM 2.1** con puntos: cilindro de `prueba.kra` a 0,945 de score.
4. **Worker** (`engine/worker.py`): servidor TCP local, protocolo JSON con
   longitud, devuelve el mejor de los 3 masks.
5. **Plugin**: selector de motor (SAM 2.1 / MobileSAM), botón para arrancar el
   worker, cliente `sam2_client.py` y respaldo automático a MobileSAM si no
   responde. `install.sh` deja la ruta del proyecto en `engine_dir`.
6. Verificado en Krita 6: `SAM 2.1: 2247x1481 en 0.45 s` y
   `2203x740 en 0.25 s` (RTX 3090). Corregido de paso `QAction` (Qt6 lo pone en
   QtGui), que rompía el atajo Ctrl+Z.

**Pendiente**

- Afinar el *prompt* (muestreo de puntos, caja) y el suavizado del alfa de SAM.
- Decidir si SAM 3 aporta con prompts por texto.
- Herramienta del toolbox y undo nativo siguen pendientes.

## 2026-11-10 — Sesión 3: máscaras ruidosas de SAM 2.1 (ronda 24)

**Síntoma**: con SAM 2.1, un solo trazo producía ruido (motas por toda la
imagen) y el objeto no aparecía.

**Causa 1 (la grave)**: doble desplazamiento. `compute()` ya convierte los trazos
a coordenadas de la capa y `_sam2_prompt` les restaba otra vez el origen del
rectángulo. Los puntos llegaban muy fuera de la imagen → SAM devolvía ruido.

**Causa 2**: elegía el candidato de mayor *score*. En esta imagen SAM puntúa alto
máscaras diminutas (0,3 % del área) y bajo las grandes: elegía la nariz o un
mechón. Ahora el worker se queda con **el mayor candidato que contiene los puntos
de primer plano** (y que no cubre casi toda la imagen).

**Causa 3**: la caja. Una caja ajustada al trazo limita a SAM y empeora el
resultado; con caja grande funcionaba a veces y otras no. Ahora se envían **solo
puntos**, muestreados (máx. ~12 por trazo).

**Verificación**: cilindro con un punto → 3,7 % (el cilindro, limpio); yeti con
punto en el pecho → 32,7 %; dentro de Krita, SAM 2.1 → 50,9 % de primer plano en
0,2 s.

## 2026-11-10 — Sesión 3: revisión y prueba completa de SAM 2.1 (ronda 25)

**Revisión de código**

- `_work_sam2` no validaba el tamaño del alfa recibido: añadida comprobación y
  registro de puntos y porcentaje.
- El alfa de SAM no pasaba por el posproceso del motor (huecos, islas,
  suavizado): ahora `rb_alpha_post` rellena huecos, desenfoca y **limpia islas
  después** del desenfoque (antes las motas del suavizado sobrevivían).
- El control "Suavizar borde" ahora también afecta a SAM 2.1 (0–16 → 0–2 px).

**Prueba completa dentro de Krita 6** (trazos simulados: cuerpo + dos pies,
4 clics de fondo): `SAM 2.1: 1024x1024 en 0.33 s`, primer plano 43,9 %, resultado
aplicado con el personaje completo (ver `tests/results/applytest2.png`).

**Valoración honesta**: el recorte es bueno para un uso real (objeto completo con
3 trazos cortos). Quedan motas diminutas junto a los pies si el trazo no los
cubre, y las zonas de pelo muy difuso aún pueden requerir Refine.

## 2026-11-10 — Sesión 4: registro de trazos del usuario (v0.3-alpha)

**Objetivo**: el usuario pinta trazos reales en Krita y el plugin los guarda
para que el desarrollo pueda reproducirlos y probarlos sin Krita.

**Hecho**

- Copia de seguridad de la versión anterior: etiqueta `v0.2-alpha-sam2` y
  `../Krita-RotoBrush-BACKUP-v0.2-alpha-sam2-20261110-090116.tar.gz`.
- Nuevo `recorder.py`: al activar la herramienta crea
  `tests/recordings/sesion-AAAAMMDD-HHMMSS/` con `meta.json` (documento,
  rect de la capa, ajustes), `strokes.jsonl` (lista COMPLETA de trazos tras
  cada trazo + % de cada máscara) y `layer.bgra` (píxeles originales).
  Activo con el marcador `~/.local/share/krita/roto_brush_record`; cualquier
  fallo del registro se ignora sin romper la herramienta.
- Arnés `tests/replay_recording.py`: carga la última grabación, arranca el
  worker SAM 2.1 si hace falta y resegmenta con prefijos 1..N trazos; guarda
  máscaras, vistas sombreadas e **IoU con la referencia de EffectCraft**.
- `tests/test_recorder.py`: sesión sintética (yeti EFFECTCRAFT, 3 trazos
  cabeza/cuerpo/pies) usada para validar el arnés.

**Descubierto con la sesión sintética** (ya reproduce la queja del usuario):

| trazos | primer plano | IoU ref |
|---|---|---|
| 1 (cabeza) | 35,5 % | 0,732 |
| 1+2 (cuerpo) | **9,7 %** | **0,206** |
| 1+2+3 (pies) | 39,8 % | 0,829 |

El segundo trazo **destruye** la máscara (solo queda la cabeza): el worker
elige «el mayor candidato que contiene TODOS los puntos de primer plano» y,
si ninguno lo cumple, cae al de mayor score (una máscara pequeña). No hay
acumulación real de trazos en SAM 2.1: cada cálculo resegmenta desde cero.

**Pendiente (v0.4)**: acumular de verdad (unir máscara previa + segmentar
solo los trazos nuevos, o caja envolvente por trazo y unión), y que el primer
trazo cubra ya el personaje entero (caja a partir del punto, no puntos sueltos).

**Flujo de pruebas**: el usuario arranca Krita, activa la herramienta, pinta y
cierra la imagen → queda una `sesion-*` nueva en `tests/recordings/` →
`.engine/venv/bin/python tests/replay_recording.py` la repite y compara.

## Sesión 5: acumulación real de trazos en SAM 2.1 (v0.4-alpha)

**Implementado** (validado en el arnés antes de tocar Krita, como acordamos):

1. **Unión acumulativa** (`compute._work_sam2`): cada trazo nuevo segmenta con
   TODOS los puntos verdes del trazo actual (contexto completo) y su máscara
   se UNE a la acumulada (`maskops._merge`, OR a nivel de bits sobre el alfa
   0/255: 3,5 ms por mega). Si un cálculo colapsa, la unión no pierde lo
   ganado. Los rojos/Refine-erase ya no llaman a SAM con negativos: restan
   SOLO su barrido local (`maskops._erase_region` + `_subtract`).
2. **Dilatación de 1 px** (`maskops._dilate1`, desplazamientos de enteros,
   11 ms): SAM recorta sistemáticamente el vello del borde; recupera 0,03 IoU.
3. `tests/replay_recording.py` replica ahora el algoritmo nuevo del plugin,
   trazo a trazo, y `tests/recordings/sesion-TEST-borra` añade un trazo rojo
   de borrado a la sesión sintética para probar la goma.

**Medido contra la referencia EFFECTCRAFT** (IoU con el alfa de la imagen):

| sesión / trazo | antes (v0.3) | ahora (v0.4) |
|---|---|---|
| 1 cabeza | 35,5 % · IoU 0,732 | igual (no hay nada que acumular) |
| +2 cuerpo | **9,7 % · 0,206 (colapso)** | 35,6 % · 0,733 |
| +3 pies | 39,8 % · 0,829 | 40,8 % · 0,841 (0,872 con dilatación) |
| +4 goma en pies | — | 39,6 % · 0,817 (quita solo el barrido) |

La goma con negativos de SAM se probó y **no funciona**: devuelve solo un
fragmento (10,3 %); el borrado local es predecible y no interfiere con la
futura integración con SAM (el video de EffectCraft hace algo mejor con los
rojos; ya se verá al analizarlo).

**Pendiente**: prueba real del usuario (reinstalar con `scripts/install.sh`
primero); análisis de los vídeos de referencia para el comportamiento de los
trazos rojos; herramienta del toolbox y undo nativo.

## Sesión 6: feedback del usuario con la v0.4 (pausamos aquí)

Pruebas reales del usuario (11:12–11:16) sobre la imagen de la chica
`assets/vu87_QWEN21_v2_e000030_01_20261029142437_1235.png` (1024x1024) y el
yeti EFFECTCRAFT, con capturas de pantalla de tres máscaras. Sesiones
grabadas: `sesion-20261110-111218` (yeti: 1 verde, 2 refine, 2 rojos, seis
máscaras sam2 siempre al 47,1 %), `sesion-20261110-111430` (chica: 2 verdes,
sam2 27,9 % → mobile 27,3 %) y `sesion-20261110-111429` **vacía** (la captura
se activó tarde y no quedó ni un trazo: el recorder volvió a fallar).

### Queja 1 — SAM 2.1 da borde de peor calidad que MobileSAM (imagen chica)

MobileSAM: silueta fina con el vello del borde conservado, mano limpia.
SAM 2.1: borde grueso y a escalones, vello segado, mano fusionada; el círculo
central es el cursor, no contaminación.

- Causa probable: el decodificador de SAM produce el mask logit a
  resolución 1/4 y lo reescala (borde en bloques); el decoder de MobileSAM
  conserva mejor el borde en este estilo de dibujo.
- Nuestra dilatación de 1 px (v0.4) empeora visualmente el grosor extra en
  imágenes donde SAM ya de por sí pasa gordo.
- Idea (v0.5): no dilatar a ciegas; refinar el borde con la propia imagen
  como guía (guided filter / CRF), o mezclar: semántica de SAM 2.1 + borde
  de MobileSAM (las dos máscaras ya se calculan baratas). Medir IoU en el
  arnés antes de decidirse.

### Queja 2 — Refine contamina el fondo con SAM 2.1

La máscara «sam2.1 + refiner» es una mancha enorme con puntos sueltos por el
fondo. En SAM 2.1 los trazos Refine entran como puntos verdes con el
contexto completo: SAM segmenta otro candidato y la unión pega la basura.

- Idea (v0.5): Refine debe refinar SOLO cerca del trazo: segimentar y
  intersectar con el vecindario barrido (radio pincel × k); nada de contexto
  global para estos trazos.

### Queja 3 — El rojo (Fondo) no quita lo que Refine ensució

El borrado local de la v0.4 quita una banda de ~32 px alrededor del trazo;
los puntos aislados y las manchas lejos del barrido quedan intactos (en la
sesión del yeti el primer plano no bajó del 47,1 % ni con dos rojos largos).

- Idea (v0.5): semántica de cubo/gota: si el rojo toca una componente
  conexa de la máscara, se va la componente ENTERA; los puntos sueltos
  pequeños deberían irse además solos (limpiar componentes < umbral).

### Pendiente para cuando retome el proyecto

1. Queja 2 y 3 juntas (refine local + rojo por componente conexa).
2. Queja 1 (borde: guided filter o fusión con MobileSAM; replantear la
   dilatación fija de 1 px).
3. Bug del recorder: la sesión de la chica con refiner (11:14) quedó vacía.
4. Revisar los vídeos de EffectCraft para el comportamiento esperado de
   Refine y Fondo.
5. Nueva función: además de quitar el fondo, ofrecer la opción de guardar
   solo la selección (la máscara como selección de Krita) para poder
   interactuar con el resto de herramientas de Krita.
6. Corregir el estado natural de Ctrl-Z: ahora no funciona, incluso cuando
   el plugin no está activo.
7. Comprobar si ComfyUI está operativo en el equipo; si lo está, usarlo
   para SAM 2.1 o SAM 3 (en caso de que estén instalados).
