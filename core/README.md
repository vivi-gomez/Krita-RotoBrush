# Motor Rust

Biblioteca compartida que hace la segmentación y el matte. Nada de UI.

## Piezas previstas (una por archivo)

| Archivo | Responsabilidad |
|---|---|
| `Cargo.toml` | Dependencias fijadas a 0.9.2 |
| `src/lib.rs` | API C: cargar modelo, calcular |
| `src/api.rs` | Conversión de buffers y errores |
| `src/engine.rs` | Trazos → `segment()` → `matte_alpha()` |
| `src/cli/` | CLI de prueba (N1) |

## Reglas

- Solo `effectcraft-*` 0.9.2; nada de PyTorch.
- La API C no expone tipos de Rust; solo punteros y números.
- Todos los archivos, cortos y con una responsabilidad.
