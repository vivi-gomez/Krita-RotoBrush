//! Trazos del usuario.

pub use effectcraft_track::roto::{Stroke, StrokeKind};

/// Un trazo con su ajuste propio de feather (`feather < 0`: usa el global).
#[derive(Clone, Debug)]
pub struct StrokeSpec {
    pub stroke: Stroke,
    pub feather: f64,
}

/// Un trazo en píxeles de imagen, en el fotograma 0.
pub fn stroke(kind: StrokeKind, points: Vec<[f64; 2]>, radius: f64) -> Stroke {
    Stroke { kind, frame: 0, radius: radius.max(0.5), points }
}

/// Trazo con feather propio.
pub fn spec(kind: StrokeKind, points: Vec<[f64; 2]>, radius: f64, feather: f64) -> StrokeSpec {
    StrokeSpec { stroke: stroke(kind, points, radius), feather }
}

/// Radio de la banda de Refine Edge (0 si no hay trazos de refinado).
pub fn refine_radius(strokes: &[StrokeSpec]) -> f64 {
    strokes
        .iter()
        .map(|s| &s.stroke)
        .filter(|s| matches!(s.kind, StrokeKind::Refine | StrokeKind::RefineErase))
        .map(|s| s.radius)
        .fold(0.0, f64::max)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn refine_radius_ignores_fg() {
        let s = vec![
            spec(StrokeKind::Fg, vec![[0.0, 0.0]], 10.0, -1.0),
            spec(StrokeKind::Refine, vec![[0.0, 0.0]], 30.0, -1.0),
            spec(StrokeKind::Refine, vec![[0.0, 0.0]], 20.0, -1.0),
        ];
        assert_eq!(refine_radius(&s), 30.0);
    }

    #[test]
    fn radius_never_zero() {
        assert_eq!(stroke(StrokeKind::Fg, vec![[0.0, 0.0]], 0.0).radius, 0.5);
    }
}

/// Puntos a lo largo de una polilínea, cada `step` píxeles.
pub(crate) fn sample_points(pts: &[[f64; 2]], step: f64) -> Vec<[f64; 2]> {
    let mut out = Vec::new();
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
            let k = i as f64 / steps as f64;
            out.push([a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k]);
        }
    }
    if let Some(last) = pts.last() {
        out.push(*last);
    }
    out
}
