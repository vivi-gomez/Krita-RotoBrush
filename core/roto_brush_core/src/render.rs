//! Del trazo al alfa: segmentar y convertir en máscara suave.

use effectcraft_raster::Image;
use effectcraft_segment::Prompt;
use effectcraft_track::roto::refine::{decontaminate, matte_alpha, MatteParams};
use effectcraft_track::roto::{rgb_of, segment, segment_with, Prior, SegOpts};

use crate::model::Model;
use crate::strokes::{refine_radius, Stroke, StrokeKind, StrokeSpec};

/// Qué calcula el alfa.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Engine {
    /// Graph cut por color, sin modelo.
    Classic,
    /// Graph cut guiado por MobileSAM (lo que usa EffectCraft).
    Model,
    /// Probabilidad de MobileSAM tal cual.
    Sam,
}

/// Ajustes del cálculo.
pub struct Params {
    pub engine: Engine,
    /// Calidad ▸ Best (más lento y más fino).
    pub best: bool,
    /// Matte y Refine Edge.
    pub refine: MatteParams,
    /// Cuánto pesa la máscara de MobileSAM frente al color (0 = sin modelo).
    pub sam_weight: f64,
    /// Radio de búsqueda de la propagación (píxeles).
    pub search_radius: f64,
    /// Quitar islas pequeñas de la máscara.
    pub clean: bool,
    /// Rellenar huecos cerrados (dibujos de líneas: contorno + relleno).
    pub fill_holes: bool,
    /// Radio del suavizado de borde con guiado por color (0 = sin suavizado).
    pub edge_smooth: usize,
    /// Máscara anterior (0–1) para no re-segmentar desde cero.
    pub prior: Option<Vec<f32>>,
    /// Peso de esa máscara anterior.
    pub prior_weight: f64,
}

impl Default for Params {
    fn default() -> Self {
        // Valores de EffectCraft para una imagen fija.
        Params {
            engine: Engine::Model,
            best: true,
            refine: MatteParams::default(),
            sam_weight: 6.0,
            search_radius: 15.0,
            clean: true,
            fill_holes: true,
            edge_smooth: 4,
            prior: None,
            prior_weight: 2.0,
        }
    }
}

/// Segmenta la imagen con esos trazos y devuelve (alfa, color descontaminado).
pub fn render_alpha_rgb(
    image: &Image,
    strokes: &[StrokeSpec],
    params: &Params,
    model: Option<&Model>,
) -> Result<(Vec<f32>, Vec<[f32; 3]>), String> {
    let (w, h) = (image.width as usize, image.height as usize);
    crate::check_size(w, h)?;
    if strokes.is_empty() {
        return Err("no hay trazos: pinta al menos un trazo de primer plano".into());
    }
    let refs: Vec<&Stroke> = strokes.iter().map(|s| &s.stroke).collect();
    let radius = refine_radius(strokes);
    if params.engine == Engine::Sam {
        let m = model.ok_or("el modo sam necesita el modelo")?;
        return Ok((m.probs(image, strokes)?, rgb_of(image)));
    }
    let opts = SegOpts {
        scale: 1.0,
        best: params.best,
        search_radius: params.search_radius.max(1.0),
        ..SegOpts::default()
    };
    let m = if params.engine == Engine::Classic { None } else { model.map(Model::as_dyn) };
    // Máscara de partida: la del cálculo anterior y/o la del modelo.
    let mut soft: Option<Vec<f32>> = params.prior.clone().filter(|p| p.len() == w * h);
    let mut weight = params.prior_weight;
    if let (Some(model), w8) = (m, params.sam_weight) {
        if w8 > 0.0 {
            let prompt = prompt_from(strokes);
            if let Ok(model_soft) = model.segment(&rgb_of(image), w, h, &prompt) {
                if model_soft.len() == w * h {
                    soft = Some(match soft {
                        Some(prev) => prev
                            .iter()
                            .zip(&model_soft)
                            .map(|(a, b)| 0.5 * a + 0.5 * b)
                            .collect(),
                        None => model_soft,
                    });
                    weight = weight.max(w8);
                }
            }
        }
    }
    let seg = match soft {
        Some(s) => {
            let prior = Prior { soft: s, fg: Default::default(), bg: Default::default(), refine: vec![0; w * h], weight };
            segment(image, &refs, Some(&prior), &opts, radius)
        }
        None => segment_with(image, &refs, None, &opts, radius, m),
    };
    if seg.matte.len() != w * h {
        return Err("la segmentación no cubre la imagen".into());
    }
    let mut rgb = rgb_of(image);
    let mut alpha = matte_alpha(&rgb, &seg, None, None, &params.refine, radius, 1.0);
    if params.edge_smooth > 0 {
        let smooth = effectcraft_track::roto::matting::guided_filter(
            &rgb, &alpha, w, h, params.edge_smooth, 1e-4,
        );
        for (a, b) in alpha.iter_mut().zip(&smooth) {
            *a = 0.5 * *a + 0.5 * *b;
        }
    }
    local_feather(&mut alpha, w, h, strokes);
    if params.fill_holes {
        fill_holes(&mut alpha, w, h);
    }
    if params.clean {
        remove_islands(&mut alpha, w, h);
    }
    if params.refine.decontaminate {
        decontaminate(&mut rgb, &alpha, &seg.refine, w, h, &params.refine, radius, 1.0);
    }
    Ok((alpha, rgb))
}

/// Máscara alfa (0–1) de la imagen con esos trazos.
pub fn render_alpha(
    image: &Image,
    strokes: &[StrokeSpec],
    params: &Params,
    model: Option<&Model>,
) -> Result<Vec<f32>, String> {
    Ok(render_alpha_rgb(image, strokes, params, model)?.0)
}

/// RGBA de salida: color original (descontaminado en el borde) y alfa de la máscara.
pub fn render_rgba(
    image: &Image,
    strokes: &[StrokeSpec],
    params: &Params,
    model: Option<&Model>,
) -> Result<Vec<u8>, String> {
    let (alpha, rgb) = render_alpha_rgb(image, strokes, params, model)?;
    let mut out = vec![0u8; alpha.len() * 4];
    for i in 0..alpha.len() {
        out[i * 4] = to_u8(rgb[i][0]);
        out[i * 4 + 1] = to_u8(rgb[i][1]);
        out[i * 4 + 2] = to_u8(rgb[i][2]);
        out[i * 4 + 3] = to_u8(alpha[i]);
    }
    Ok(out)
}

fn to_u8(v: f32) -> u8 {
    (v.clamp(0.0, 1.0) * 255.0).round() as u8
}

/// Imagen del motor desde píxeles RGBA entrelazados (8 bits).
/// `swap_rb`: los bytes vienen en orden BGRA (Krita).
pub fn image_from_rgba(bytes: &[u8], w: usize, h: usize) -> Result<Image, String> {
    image_from_bytes(bytes, w, h, false)
}

/// Igual que [`image_from_rgba`], con orden de canales configurable.
pub fn image_from_bytes(bytes: &[u8], w: usize, h: usize, bgra: bool) -> Result<Image, String> {
    crate::check_size(w, h)?;
    if bytes.len() < w * h * 4 {
        return Err(format!(
            "faltan píxeles: hay {} bytes y hacen falta {}",
            bytes.len(),
            w * h * 4
        ));
    }
    let mut image = Image::new(w as u32, h as u32);
    for i in 0..w * h {
        let a = bytes[i * 4 + 3] as f32 / 255.0;
        // El motor guarda color premultiplicado; con alfa 0 el RGB da igual.
        let (r, g, b) = if bgra {
            (bytes[i * 4 + 2], bytes[i * 4 + 1], bytes[i * 4])
        } else {
            (bytes[i * 4], bytes[i * 4 + 1], bytes[i * 4 + 2])
        };
        image.data[i] = [r as f32 / 255.0 * a, g as f32 / 255.0 * a, b as f32 / 255.0 * a, a];
    }
    Ok(image)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_rgba() {
        let px = [10u8, 20, 30, 255, 40, 50, 60, 0];
        let img = image_from_rgba(&px, 2, 1).unwrap();
        assert_eq!((img.width, img.height), (2, 1));
        assert!((img.data[0][0] - 10.0 / 255.0).abs() < 1e-6);
        assert_eq!(img.data[1][3], 0.0);
    }

    #[test]
    fn rejects_short_buffers() {
        assert!(image_from_rgba(&[0; 4], 2, 1).is_err());
        assert!(image_from_rgba(&[0; 4], 0, 0).is_err());
    }
}

/// Puntos de la indicación para el modelo: a lo largo de los trazos FG/BG.
fn prompt_from(strokes: &[StrokeSpec]) -> Prompt {
    let mut points = Vec::new();
    for spec in strokes {
        let s = &spec.stroke;
        let fg = match s.kind {
            StrokeKind::Fg => true,
            StrokeKind::Bg => false,
            _ => continue,
        };
        for p in crate::strokes::sample_points(&s.points, 12.0) {
            points.push(([p[0] as f32, p[1] as f32], fg));
        }
    }
    Prompt { points, bbox: None, mask: None }
}

/// Elimina componentes conexas pequeñas del primer plano (fugas del graph cut).
pub(crate) fn remove_islands(alpha: &mut [f32], w: usize, h: usize) {
    let n = w * h;
    if n == 0 || alpha.len() != n {
        return;
    }
    let min_area = ((n as f64) * 0.0008).max(24.0) as usize;
    let mut seen = vec![false; n];
    let mut stack = Vec::new();
    let mut comp = Vec::new();
    for start in 0..n {
        if seen[start] || alpha[start] < 0.5 {
            continue;
        }
        stack.clear();
        comp.clear();
        stack.push(start);
        seen[start] = true;
        while let Some(i) = stack.pop() {
            comp.push(i);
            let (x, y) = (i % w, i / w);
            let mut push = |j: usize, seen: &mut Vec<bool>, stack: &mut Vec<usize>| {
                if !seen[j] && alpha[j] >= 0.5 {
                    seen[j] = true;
                    stack.push(j);
                }
            };
            if x > 0 { push(i - 1, &mut seen, &mut stack); }
            if x + 1 < w { push(i + 1, &mut seen, &mut stack); }
            if y > 0 { push(i - w, &mut seen, &mut stack); }
            if y + 1 < h { push(i + w, &mut seen, &mut stack); }
        }
        if comp.len() < min_area {
            for i in comp.drain(..) {
                alpha[i] = 0.0;
            }
        }
    }
}

/// Rellena los huecos cerrados: lo que no se alcanza desde el borde es objeto.
pub(crate) fn fill_holes(alpha: &mut [f32], w: usize, h: usize) {
    let n = w * h;
    if n == 0 || alpha.len() != n {
        return;
    }
    let mut seen = vec![false; n];
    let mut stack: Vec<usize> = Vec::new();
    let mut push = |i: usize, seen: &mut Vec<bool>, stack: &mut Vec<usize>| {
        if !seen[i] && alpha[i] < 0.5 {
            seen[i] = true;
            stack.push(i);
        }
    };
    for x in 0..w {
        push(x, &mut seen, &mut stack);
        push((h - 1) * w + x, &mut seen, &mut stack);
    }
    for y in 0..h {
        push(y * w, &mut seen, &mut stack);
        push(y * w + w - 1, &mut seen, &mut stack);
    }
    while let Some(i) = stack.pop() {
        let (x, y) = (i % w, i / w);
        if x > 0 { push(i - 1, &mut seen, &mut stack); }
        if x + 1 < w { push(i + 1, &mut seen, &mut stack); }
        if y > 0 { push(i - w, &mut seen, &mut stack); }
        if y + 1 < h { push(i + w, &mut seen, &mut stack); }
    }
    for i in 0..n {
        if !seen[i] && alpha[i] < 0.5 {
            alpha[i] = 1.0;
        }
    }
}

/// Feather propio de cada trazo: suaviza el alfa solo alrededor de ese trazo.
fn local_feather(alpha: &mut [f32], w: usize, h: usize, strokes: &[StrokeSpec]) {
    use effectcraft_track::roto::matting::gauss;
    use effectcraft_track::roto::rasterize;

    for spec in strokes.iter().filter(|s| s.feather > 0.0) {
        let band = rasterize(&[&spec.stroke], &[spec.stroke.kind], 1.0, w, h);
        if !band.iter().any(|v| *v) {
            continue;
        }
        let mask: Vec<f32> = band.iter().map(|v| if *v { 1.0 } else { 0.0 }).collect();
        // Influencia amplia: llega al borde cercano al trazo, no solo a su banda.
        let influence = (spec.stroke.radius * 3.0 + spec.feather * 4.0).max(8.0);
        let mut falloff = gauss(&mask, w, h, influence / 2.0);
        let peak = falloff.iter().copied().fold(0.0f32, f32::max);
        if peak > 1e-6 {
            for v in falloff.iter_mut() {
                *v /= peak;
            }
        }
        let blurred = gauss(alpha, w, h, spec.feather / 2.0);
        for i in 0..alpha.len() {
            let k = falloff[i].clamp(0.0, 1.0);
            if k > 0.0 {
                alpha[i] += (blurred[i] - alpha[i]) * k;
            }
        }
    }
}
