# Objetivo

## Qué es

Un plugin de Krita que añade una herramienta de recorte (tipo *roto brush*) y un
docker de ajustes. El usuario marca con el pincel lo que quiere conservar; el
plugin localiza el objeto completo y deja el fondo en transparencia **en la
misma capa**.

## Flujo de uso

1. El usuario abre la imagen y selecciona la capa a tratar.
2. Activa **Roto Brush** en la caja de herramientas.
3. Pinta trazos de primer plano sobre el personaje (verde) y, con Alt, trazos de
   fondo sobre lo que debe desaparecer (rojo).
4. En zonas difíciles (pelo, bordes difusos) usa el pincel **Refine Edge**.
5. Ajusta en el docker: Feather, Contrast, Shift, Smooth, Higher Quality,
   Decontaminate…
6. Pulsa **Aplicar**: el alfa se escribe en la capa activa; el fondo queda
   transparente.

## Requisitos funcionales

- FR1 Herramienta visible en la caja de herramientas de Krita 5 y 6.
- FR2 Docker con los ajustes de la herramienta, actualizables en caliente.
- FR3 Trazos acumulativos FG/BG/Refine; Alt invierte a fondo; Deshacer/Borrar.
- FR4 Segmentación automática del objeto a partir de los trazos.
- FR5 Refinado de bordes y pelo (banda de Refine Edge).
- FR6 Resultado en la capa original, sin capas auxiliares ni previews.
- FR7 Ninguna ruta de usuario ni dato sensible en el repositorio.

## Fuera de alcance (v1)

- Vídeo, tracking entre fotogramas, *propagation* temporal.
- SAM 2.1 y modelos distintos de MobileSAM.
- Edición de varias capas a la vez o de grupos.

## Criterios de aceptación

1. En Krita 5 y 6, el botón aparece en el toolbox y activa el modo pincel.
2. Pintar FG/BG y pulsar Aplicar produce una transparencia limpia en el borde.
3. El pelo se resuelve con Refine Edge sin halos ni bloques.
4. La operación no crea capas nuevas ni deja restos en el documento.
5. Todo el proceso va en hilo de trabajo: la UI no se congela.
