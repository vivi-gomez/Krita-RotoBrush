//! Motor del Roto Brush: segmentación interactiva y matte suave.
//!
//! Envuelve los crates de EffectCraft (`effectcraft-track`, `effectcraft-segment`).
//! No hay UI ni E/S de Krita aquí: entra una imagen y unos trazos, sale un alfa.

pub mod ffi;
pub mod model;
pub mod render;
pub mod strokes;

pub use model::Model;
pub use render::{render_rgba, Engine, Params};
pub use strokes::{spec, stroke, Stroke, StrokeKind, StrokeSpec};

/// Comprueba que una máscara tiene el tamaño esperado.
pub(crate) fn check_size(w: usize, h: usize) -> Result<(), String> {
    if w == 0 || h == 0 {
        return Err("la imagen no tiene tamaño".into());
    }
    Ok(())
}
