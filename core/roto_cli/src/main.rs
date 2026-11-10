//! CLI de prueba del motor, sin Krita.

mod args;
mod png_io;

use roto_brush_core::{render, Model};

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let a = args::Args::parse(std::env::args().skip(1))?;
    let (rgba, w, h) = png_io::read(&a.image)?;
    println!("imagen {}x{} ({} bytes)", w, h, rgba.len());

    let t0 = std::time::Instant::now();
    let model = if a.no_model {
        println!("sin modelo: graph cut clásico");
        None
    } else {
        let m = Model::from_file(&a.model)?;
        println!("modelo: {} cargado en {:.2} s", m.name(), t0.elapsed().as_secs_f64());
        Some(m)
    };

    let image = render::image_from_rgba(&rgba, w, h)?;
    let t1 = std::time::Instant::now();
    let out = render::render_rgba(&image, &a.strokes, &a.params, model.as_ref())?;
    let secs = t1.elapsed().as_secs_f64();

    png_io::write(&a.out, &out, w, h)?;
    let alpha: Vec<u8> = out.chunks_exact(4).map(|p| p[3]).collect();
    let fg = alpha.iter().filter(|v| **v > 127).count() as f64 / alpha.len() as f64;
    let mean = alpha.iter().map(|v| *v as f64).sum::<f64>() / alpha.len() as f64;
    println!(
        "listo en {secs:.2} s: primer plano {:.1} %, alfa medio {:.1} de 255 -> {}",
        fg * 100.0,
        mean,
        a.out.display()
    );
    Ok(())
}
