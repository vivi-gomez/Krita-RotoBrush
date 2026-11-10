//! Argumentos del CLI.

use std::path::PathBuf;

use roto_brush_core::{spec, Engine, Params, StrokeKind, StrokeSpec};

pub struct Args {
    pub image: PathBuf,
    pub out: PathBuf,
    pub model: PathBuf,
    pub strokes: Vec<StrokeSpec>,
    pub params: Params,
    pub no_model: bool,
}

impl Args {
    pub fn parse(mut it: impl Iterator<Item = String>) -> Result<Args, String> {
        let (mut image, mut out, mut model) = (None, None, None);
        let (mut fg, mut bg, mut refine, mut erase) = (Vec::new(), Vec::new(), Vec::new(), Vec::new());
        let (mut brush, mut band) = (12.0f64, 20.0f64);
        let mut params = Params::default();
        let mut no_model = false;
        let mut stroke_feather = -1.0f64;

        while let Some(flag) = it.next() {
            let mut val = || it.next().ok_or_else(|| format!("falta el valor de {flag}"));
            match flag.as_str() {
                "--image" => image = Some(PathBuf::from(val()?)),
                "--out" => out = Some(PathBuf::from(val()?)),
                "--model" => model = Some(PathBuf::from(val()?)),
                "--fg" => fg = paths(&val()?)?,
                "--bg" => bg = paths(&val()?)?,
                "--refine" => refine = paths(&val()?)?,
                "--refine-erase" => erase = paths(&val()?)?,
                "--engine" => {
                    params.engine = match val()?.as_str() {
                        "classic" => Engine::Classic,
                        "model" => Engine::Model,
                        "sam" => Engine::Sam,
                        other => return Err(format!("motor desconocido: {other}")),
                    }
                }
                "--brush" => brush = num(&val()?)?,
                "--refine-radius" => band = num(&val()?)?,
                "--feather" => params.refine.feather = num(&val()?)?,
                "--smooth" => params.refine.smooth = num(&val()?)?,
                "--shift" => params.refine.shift = num(&val()?)?,
                "--contrast" => params.refine.contrast = num(&val()?)?,
                "--sam-weight" => params.sam_weight = num(&val()?)?,
                "--no-model" => no_model = true,
                "--no-best" => params.best = false,
                "--no-decontaminate" => params.refine.decontaminate = false,
                "--stroke-feather" => stroke_feather = num(&val()?)?,
                "--edge-smooth" => params.edge_smooth = num(&val()?)?.max(0.0) as usize,
                "--no-fill" => params.fill_holes = false,
                "--no-clean" => params.clean = false,
                "-h" | "--help" => return Err(HELP.into()),
                other => return Err(format!("opción desconocida: {other}")),
            }
        }

        let image = image.ok_or("falta --image")?;
        let out = out.ok_or("falta --out")?;
        let model = model.unwrap_or_else(default_model);
        let mut strokes = Vec::new();
        for (kind, polylines) in [
            (StrokeKind::Fg, fg),
            (StrokeKind::Bg, bg),
            (StrokeKind::Refine, refine),
            (StrokeKind::RefineErase, erase),
        ] {
            let radius = if matches!(kind, StrokeKind::Refine | StrokeKind::RefineErase) { band } else { brush };
            for pts in polylines {
                strokes.push(spec(kind, pts, radius, stroke_feather));
            }
        }
        Ok(Args { image, out, model, strokes, params, no_model })
    }
}

fn default_model() -> PathBuf {
    if let Ok(p) = std::env::var("ROTO_BRUSH_MODEL") {
        return PathBuf::from(p);
    }
    let home = std::env::var("HOME").unwrap_or_default();
    PathBuf::from(home).join(".config/effectcraft/models/mobile_sam.pt")
}

/// "x,y;x,y|u,v;u,v" -> varias polilíneas.
fn paths(s: &str) -> Result<Vec<Vec<[f64; 2]>>, String> {
    s.split('|').filter(|p| !p.trim().is_empty()).map(points).collect()
}

fn points(s: &str) -> Result<Vec<[f64; 2]>, String> {
    let mut out = Vec::new();
    for pair in s.split(';').filter(|p| !p.trim().is_empty()) {
        let (x, y) = pair.split_once(',').ok_or_else(|| format!("punto no válido: {pair}"))?;
        out.push([num(x)?, num(y)?]);
    }
    Ok(out)
}

fn num(s: &str) -> Result<f64, String> {
    s.trim().parse().map_err(|_| format!("número no válido: {s}"))
}

const HELP: &str = "\
roto_cli --image entrada.png --out salida.png [opciones]

  --model RUTA          mobile_sam.pt (por defecto: ROTO_BRUSH_MODEL o la carpeta de EffectCraft)
  --fg \"x,y;x,y|u,v\"    trazos de primer plano (| separa trazos)
  --bg \"...\"            trazos de fondo
  --refine \"...\"        banda de Refine Edge (pelo, bordes)
  --refine-erase \"...\"  quitar de la banda
  --engine classic|model|sam
  --brush N             radio del pincel FG/BG (por defecto 12)
  --refine-radius N     radio de la banda (por defecto 20)
  --feather N --smooth N --shift N --contrast N
  --stroke-feather N    feather propio de cada trazo (0 = heredar)
  --edge-smooth N       radio de suavizado de borde (0 = ninguno)
  --no-model --no-best --no-decontaminate";
