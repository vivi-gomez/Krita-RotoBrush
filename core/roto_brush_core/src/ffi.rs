//! API C estable para llamar al motor desde el plugin de Krita (ctypes).

use std::ffi::{c_char, CStr, CString};
use std::slice;

use effectcraft_track::roto::refine::MatteParams;

use crate::model::Model;
use crate::render::{render_rgba, Engine, Params};
use crate::strokes::{spec, StrokeKind};

/// Ajustes que llegan desde Python.
#[repr(C)]
pub struct RbParams {
    /// 0 = classic, 1 = model, 2 = sam.
    pub engine: i32,
    pub best: i32,
    pub feather: f32,
    pub smooth: f32,
    pub shift: f32,
    pub contrast: f32,
    pub decontaminate: i32,
    /// Los bytes vienen en BGRA (Krita).
    pub bgra: i32,
    /// Peso de la máscara del modelo frente al color.
    pub sam_weight: f32,
    /// Radio de búsqueda (propagación).
    pub search_radius: f32,
    /// Quitar islas pequeñas.
    pub clean: i32,
    /// Rellenar huecos cerrados.
    pub fill_holes: i32,
    /// Máscara del cálculo anterior (w*h bytes) o NULL.
    pub prior: *const u8,
    pub prior_len: usize,
    /// Peso de la máscara anterior.
    pub prior_weight: f32,
    /// Radio de suavizado de borde (0 = ninguno).
    pub edge_smooth: i32,
}

fn err_set(buf: *mut c_char, len: usize, msg: &str) {
    if buf.is_null() || len == 0 {
        return;
    }
    let c = CString::new(msg).unwrap_or_default();
    let b = c.as_bytes();
    let n = b.len().min(len - 1);
    unsafe {
        std::ptr::copy_nonoverlapping(b.as_ptr(), buf as *mut u8, n);
        *buf.add(n) = 0;
    }
}

/// Carga el modelo desde una ruta UTF-8. Devuelve NULL si falla.
#[no_mangle]
pub extern "C" fn rb_model_load(path: *const c_char) -> *mut Model {
    if path.is_null() {
        return std::ptr::null_mut();
    }
    let Ok(s) = unsafe { CStr::from_ptr(path) }.to_str() else {
        return std::ptr::null_mut();
    };
    match Model::from_file(std::path::Path::new(s)) {
        Ok(m) => Box::into_raw(Box::new(m)),
        Err(_) => std::ptr::null_mut(),
    }
}

#[no_mangle]
pub extern "C" fn rb_model_free(m: *mut Model) {
    if !m.is_null() {
        unsafe {
            drop(Box::from_raw(m));
        }
    }
}

#[no_mangle]
pub extern "C" fn rb_version() -> *const c_char {
    static V: &[u8] = b"0.1.0\0";
    V.as_ptr() as *const c_char
}

/// Calcula el alfa de una imagen RGBA (8 bits) con unos trazos.
///
/// `strokes` es una secuencia plana `[kind, radius, n, x0, y0, ...]` repetida.
/// `out_alpha` debe tener `w*h` bytes. Devuelve 0 si todo va bien, -1 si no.
#[no_mangle]
pub extern "C" fn rb_render(
    model: *const Model,
    rgba: *const u8,
    w: u32,
    h: u32,
    strokes: *const f32,
    strokes_len: usize,
    p: *const RbParams,
    out_alpha: *mut u8,
    out_len: usize,
    err: *mut c_char,
    err_len: usize,
) -> i32 {
    if rgba.is_null() || out_alpha.is_null() || p.is_null() {
        err_set(err, err_len, "puntero nulo");
        return -1;
    }
    let (w, h) = (w as usize, h as usize);
    if w == 0 || h == 0 || out_len < w * h {
        err_set(err, err_len, "tamaño de imagen no válido");
        return -1;
    }
    let px = unsafe { slice::from_raw_parts(rgba, w * h * 4) };
    let params = unsafe { &*p };
    let engine = match params.engine {
        0 => Engine::Classic,
        2 => Engine::Sam,
        _ => Engine::Model,
    };
    let refine = MatteParams {
        feather: params.feather.max(0.0) as f64,
        smooth: params.smooth.max(0.0) as f64,
        shift: params.shift as f64,
        contrast: params.contrast as f64,
        decontaminate: params.decontaminate != 0,
        ..MatteParams::default()
    };
    let cfg = Params {
        engine,
        best: params.best != 0,
        refine,
        sam_weight: params.sam_weight as f64,
        search_radius: params.search_radius as f64,
        clean: params.clean != 0,
        fill_holes: params.fill_holes != 0,
        prior: if params.prior.is_null() || params.prior_len < w * h {
            None
        } else {
            Some(unsafe { slice::from_raw_parts(params.prior, w * h) }
                .iter()
                .map(|v| *v as f32 / 255.0)
                .collect())
        },
        prior_weight: params.prior_weight as f64,
        edge_smooth: params.edge_smooth.max(0) as usize,
    };

    let Ok(strokes) = parse_strokes(strokes, strokes_len) else {
        err_set(err, err_len, "trazos mal formados");
        return -1;
    };
    let image = match crate::render::image_from_bytes(px, w, h, params.bgra != 0) {
        Ok(i) => i,
        Err(e) => {
            err_set(err, err_len, &e);
            return -1;
        }
    };
    let m = unsafe { model.as_ref() };
    let out = match render_rgba(&image, &strokes, &cfg, m) {
        Ok(v) => v,
        Err(e) => {
            err_set(err, err_len, &e);
            return -1;
        }
    };
    let alpha = unsafe { slice::from_raw_parts_mut(out_alpha, w * h) };
    for (i, a) in alpha.iter_mut().enumerate() {
        *a = out[i * 4 + 3];
    }
    0
}

/// Máscara de atenuación para la vista previa: `out_rgba` recibe color donde el
/// alfa es bajo (fondo) y transparente donde el objeto se conserva.
#[no_mangle]
pub extern "C" fn rb_dim_mask(
    alpha: *const u8,
    w: u32,
    h: u32,
    out_rgba: *mut u8,
    r: u8,
    g: u8,
    b: u8,
    a: u8,
) -> i32 {
    if alpha.is_null() || out_rgba.is_null() || w == 0 || h == 0 {
        return -1;
    }
    let n = (w as usize) * (h as usize);
    let src = unsafe { slice::from_raw_parts(alpha, n) };
    let dst = unsafe { slice::from_raw_parts_mut(out_rgba, n * 4) };
    for i in 0..n {
        // Atenuación proporcional al alfa: los bordes suaves se ven suaves.
        let k = 255 - src[i] as u32;
        let out_a = (k * a as u32 / 255) as u8;
        let px = if out_a > 0 { [r, g, b, out_a] } else { [0, 0, 0, 0] };
        dst[i * 4..i * 4 + 4].copy_from_slice(&px);
    }
    0
}

/// Máscara en blanco y negro (gris = feather) para verla sin la imagen.
#[no_mangle]
pub extern "C" fn rb_gray_mask(alpha: *const u8, w: u32, h: u32, out_rgba: *mut u8) -> i32 {
    if alpha.is_null() || out_rgba.is_null() || w == 0 || h == 0 {
        return -1;
    }
    let n = (w as usize) * (h as usize);
    let src = unsafe { slice::from_raw_parts(alpha, n) };
    let dst = unsafe { slice::from_raw_parts_mut(out_rgba, n * 4) };
    for i in 0..n {
        let v = src[i];
        dst[i * 4..i * 4 + 4].copy_from_slice(&[v, v, v, 255]);
    }
    0
}

/// `[kind, radius, n, (x, y) * n]...` -> trazos.
fn parse_strokes(buf: *const f32, len: usize) -> Result<Vec<crate::StrokeSpec>, ()> {
    if len == 0 || buf.is_null() {
        return Ok(Vec::new());
    }
    let data = unsafe { slice::from_raw_parts(buf, len) };
    let mut out = Vec::new();
    let mut i = 0;
    while i + 4 <= data.len() {
        let kind = match data[i] as i32 {
            0 => StrokeKind::Fg,
            1 => StrokeKind::Bg,
            2 => StrokeKind::Refine,
            3 => StrokeKind::RefineErase,
            _ => return Err(()),
        };
        let radius = data[i + 1] as f64;
        let feather = data[i + 2] as f64;
        let n = data[i + 3] as i32;
        i += 4;
        if n < 0 || (n as usize) * 2 > data.len() - i {
            return Err(());
        }
        let mut pts = Vec::with_capacity(n as usize);
        for k in 0..n as usize {
            pts.push([data[i + k * 2] as f64, data[i + k * 2 + 1] as f64]);
        }
        i += n as usize * 2;
        out.push(spec(kind, pts, radius, feather));
    }
    Ok(out)
}

/// Posproceso de un alfa externo (p. ej. SAM 2.1): rellena huecos, quita islas
/// y aplica un desenfoque suave. `alpha` es w*h bytes y se modifica en sitio.
#[no_mangle]
pub extern "C" fn rb_alpha_post(
    alpha: *mut u8,
    w: u32,
    h: u32,
    fill: i32,
    clean: i32,
    blur: f32,
) -> i32 {
    if alpha.is_null() || w == 0 || h == 0 {
        return -1;
    }
    let n = (w as usize) * (h as usize);
    let src = unsafe { slice::from_raw_parts(alpha, n) };
    let mut a: Vec<f32> = src.iter().map(|v| *v as f32 / 255.0).collect();
    let w = w as usize;
    let h = h as usize;
    if fill != 0 {
        crate::render::fill_holes(&mut a, w, h);
    }
    if blur > 0.0 {
        a = effectcraft_track::roto::matting::gauss(&a, w, h, blur as f64);
    }
    // Después del desenfoque: así también caen las motas que el suavizado creó.
    if clean != 0 {
        crate::render::remove_islands(&mut a, w, h);
    }
    let dst = unsafe { slice::from_raw_parts_mut(alpha, n) };
    for (d, v) in dst.iter_mut().zip(&a) {
        *d = (v.clamp(0.0, 1.0) * 255.0).round() as u8;
    }
    0
}
