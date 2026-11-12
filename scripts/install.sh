#!/usr/bin/env bash
# Instala Roto Brush en el perfil de usuario de Krita. Sin root, sin tocar Krita.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KB="$HOME/.local/share/krita/pykrita/roto_brush"
KD="$HOME/.local/share/krita/pykrita/roto_brush.desktop"
KC="$HOME/.config/kritarc"
LIB="$REPO/core/target/release/libroto_brush_core.so"

if [ ! -f "$LIB" ]; then
  echo "Falta el motor. Compílalo antes:  cd core && cargo build --release" >&2
  exit 1
fi

mkdir -p "$KB/lib"
# Copia limpia: sin __pycache__ viejo ni módulos que ya no existen en el repo
# (una goma antigua instalada parece "arreglada" y no lo está: sesión 8).
rm -rf "$KB/__pycache__"
find "$KB" -maxdepth 1 -name '*.py' -delete
cp -r "$REPO/pykrita/roto_brush/." "$KB/"
rm -rf "$KB/__pycache__"
rm -f "$KB/lib/libroto_brush_core.so"
cp "$LIB" "$KB/lib/"
cp "$REPO/pykrita/roto_brush.desktop" "$KD"
printf '%s\n' "$REPO" > "$KB/engine_dir"

if [ -f "$KC" ] && ! grep -q "^enable_roto_brush=" "$KC"; then
  cp "$KC" "$KC.backup_roto_brush"
  if grep -q "^\[python\]" "$KC"; then
    sed -i '/^\[python\]/a enable_roto_brush=true' "$KC"
  else
    printf '\n[python]\nenable_roto_brush=true\n' >> "$KC"
  fi
fi

echo "Instalado en $KB"
echo "En Krita: Configuración > Dockers > Roto Brush"
