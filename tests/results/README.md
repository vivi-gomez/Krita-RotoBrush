# Resultados N1 (motor, 2026-11-08)

Imagen: `assets/Krea2_turbo_style_reference_00001_.png` (1024×1024).
Modelo: `mobile_sam.pt`. CPU, 48 hilos. `--best` activo.

## Ejecuciones

| Archivo | Motor | Trazos | Tiempo | FG | Veredicto |
|---|---|---|---|---|---|
| `fg_bg.png` | model | 1 polilínea FG + 1 BG | 1.64 s | 17 % | **Mal**: huecos en diagonal por la polilínea |
| `classic.png` | classic | idem | 1.03 s | 21 % | Mal: falta cuerpo y patas |
| `v2_classic.png` | classic | 8 FG + 5 BG | 0.90 s | 47 % | Bien, con resto verde abajo |
| `v2_model.png` | model | 8 FG + 5 BG | 1.46 s | 44 % | Bien, pierde el cuerno izquierdo |
| `v3_model.png` | model | 9 FG + 6 BG, feather 1.2 | 1.43 s | 45 % | **Mejor**: cuernos, patas, libro |
| `v3_refine.png` | model | + banda Refine (brazo) | 2.27 s | 45 % | Igual: la banda no tocaba borde |
| `v4_refine.png` | model | + banda Refine (pelo) | 2.55 s | 45 % | La banda actúa, pero con halo |

## Lo aprendido

1. **Un trazo = un trazo.** Encadenar puntos en una sola polilínea pinta una
   banda entre ellos; si cruza el fondo, el resultado se rompe. En la UI cada
   trazo del pincel será independiente.
2. **Modelo + graph cut** recupera zonas que el color no distingue (pelo verde
   sobre fondo verde): conserva cuernos y patas que el modo clásico perdía.
3. **Refine Edge** funciona (cambia el resultado y tarda más), pero una banda
   ancha con `smooth` alto deja halo. Hay que ajustar valores por defecto.
4. Velocidad de sobra: 0.5–2.5 s por cálculo en CPU.

## Reproducir

```
cd core
cargo build --release
./target/release/roto_cli --image ../assets/Krea2_turbo_style_reference_00001_.png \
  --out ../tests/results/salida.png --engine model \
  --fg "330,190|512,330|512,440|330,560|720,560|512,760|300,880|740,880|450,700" \
  --bg "60,60|960,60|60,960|960,960|512,60|120,930" --brush 18 --feather 1.2
```

Las imágenes de salida no se versionan (ver `.gitignore`).
