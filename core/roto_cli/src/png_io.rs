//! Lectura y escritura de PNG (RGBA de 8 bits).

use std::path::Path;

pub fn read(path: &Path) -> Result<(Vec<u8>, usize, usize), String> {
    let file = std::fs::File::open(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let decoder = png::Decoder::new(std::io::BufReader::new(file));
    let mut reader = decoder.read_info().map_err(|e| format!("{}: {e}", path.display()))?;
    let mut buf = vec![0u8; reader.output_buffer_size()];
    let info = reader.next_frame(&mut buf).map_err(|e| format!("{}: {e}", path.display()))?;
    let (w, h) = (info.width as usize, info.height as usize);
    let px = to_rgba(&buf, &info)?;
    Ok((px, w, h))
}

fn to_rgba(buf: &[u8], info: &png::OutputInfo) -> Result<Vec<u8>, String> {
    let bpp: usize = match info.color_type {
        png::ColorType::Grayscale => 1,
        png::ColorType::GrayscaleAlpha => 2,
        png::ColorType::Rgb => 3,
        png::ColorType::Rgba => 4,
        png::ColorType::Indexed => return Err("PNG con paleta: no soportado".into()),
    };
    let step = match info.bit_depth {
        png::BitDepth::Eight => 1,
        png::BitDepth::Sixteen => 2,
        _ => return Err("profundidad de color no soportada".into()),
    };
    let n = info.width as usize * info.height as usize;
    let mut out = vec![0u8; n * 4];
    for i in 0..n {
        let s = i * bpp * step;
        let g = |k: usize| buf[s + k * step];
        let (r, gg, b, a) = match info.color_type {
            png::ColorType::Grayscale => (g(0), g(0), g(0), 255),
            png::ColorType::GrayscaleAlpha => (g(0), g(0), g(0), g(1)),
            png::ColorType::Rgb => (g(0), g(1), g(2), 255),
            png::ColorType::Rgba => (g(0), g(1), g(2), g(3)),
            png::ColorType::Indexed => unreachable!("filtrado antes"),
        };
        out[i * 4..i * 4 + 4].copy_from_slice(&[r, gg, b, a]);
    }
    Ok(out)
}

pub fn write(path: &Path, rgba: &[u8], w: usize, h: usize) -> Result<(), String> {
    let file = std::fs::File::create(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut enc = png::Encoder::new(std::io::BufWriter::new(file), w as u32, h as u32);
    enc.set_color(png::ColorType::Rgba);
    enc.set_depth(png::BitDepth::Eight);
    let mut writer = enc.write_header().map_err(|e| format!("{}: {e}", path.display()))?;
    writer.write_image_data(rgba).map_err(|e| format!("{}: {e}", path.display()))?;
    Ok(())
}
