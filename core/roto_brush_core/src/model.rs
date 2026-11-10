//! Carga del modelo de segmentación (MobileSAM).

use std::path::Path;
use std::sync::Arc;

use effectcraft_raster::Image;
use effectcraft_segment::{load, Loaded, MaskModel, Prompt};

/// Modelo cargado y listo para segmentar.
pub struct Model {
    inner: Arc<dyn MaskModel>,
}

impl Model {
    /// Carga desde los bytes del checkpoint `mobile_sam.pt`.
    /// El crate verifica el SHA-256 contra el registro oficial.
    pub fn from_bytes(bytes: &[u8]) -> Result<Model, String> {
        match load("mobilesam", bytes).map_err(|e| format!("modelo no válido: {e}"))? {
            Loaded::Mask(inner) => Ok(Model { inner }),
            _ => Err("el modelo cargado no es de segmentación".into()),
        }
    }

    /// Carga desde un archivo.
    pub fn from_file(path: &Path) -> Result<Model, String> {
        let bytes = std::fs::read(path)
            .map_err(|e| format!("no se pudo leer {}: {e}", path.display()))?;
        Model::from_bytes(&bytes)
    }

    pub fn name(&self) -> &'static str {
        self.inner.info().name
    }

    pub(crate) fn as_dyn(&self) -> &dyn MaskModel {
        self.inner.as_ref()
    }

    /// Probabilidad de primer plano que da el modelo, sin graph cut.
    pub fn probs(&self, image: &Image, strokes: &[crate::StrokeSpec]) -> Result<Vec<f32>, String> {
        let (w, h) = (image.width as usize, image.height as usize);
        crate::check_size(w, h)?;
        let rgb: Vec<[f32; 3]> = image
            .data
            .iter()
            .map(|p| if p[3] > 1e-6 { [p[0] / p[3], p[1] / p[3], p[2] / p[3]] } else { [0.0; 3] })
            .collect();
        let mut points = Vec::new();
        for spec in strokes {
            let s = &spec.stroke;
            if !matches!(s.kind, crate::StrokeKind::Fg | crate::StrokeKind::Bg) {
                continue;
            }
            let fg = s.kind == crate::StrokeKind::Fg;
            for p in sample(s, 8.0) {
                points.push(([p[0] as f32, p[1] as f32], fg));
            }
        }
        if points.is_empty() {
            return Err("no hay puntos de primer plano".into());
        }
        let prompt = Prompt { points, bbox: None, mask: None };
        self.inner.segment(&rgb, w, h, &prompt)
    }
}

/// Puntos a lo largo de una polilínea, cada `step` píxeles.
fn sample(s: &crate::Stroke, step: f64) -> Vec<[f64; 2]> {
    let mut out = Vec::new();
    let pts = &s.points;
    if pts.is_empty() {
        return out;
    }
    if pts.len() == 1 {
        return vec![pts[0]];
    }
    for pair in pts.windows(2) {
        let (a, b) = (pair[0], pair[1]);
        let len = ((b[0] - a[0]).powi(2) + (b[1] - a[1]).powi(2)).sqrt();
        if len < 1e-6 {
            continue;
        }
        let steps = (len / step).ceil().max(1.0) as usize;
        for i in 0..steps {
            let t = i as f64 / steps as f64;
            out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
        }
    }
    out.push(*pts.last().unwrap_or(&pts[0]));
    out
}
