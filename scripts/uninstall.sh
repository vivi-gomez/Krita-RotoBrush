#!/usr/bin/env bash
# Quita Roto Brush del perfil de usuario de Krita. No toca otras extensiones
# ni borra nada de tus imágenes; guarda una copia de kritarc antes de quitar
# la línea que activa el plugin.
set -euo pipefail

KB="$HOME/.local/share/krita/pykrita/roto_brush"
KD="$HOME/.local/share/krita/pykrita/roto_brush.desktop"
KC="$HOME/.config/kritarc"

if [ ! -e "$KB" ] && [ ! -e "$KD" ]; then
  echo "No había nada instalado."
fi

rm -rf "$KB" "$KD"

if [ -f "$KC" ] && grep -q "^enable_roto_brush=" "$KC"; then
  cp "$KC" "$KC.backup_roto_brush"
  sed -i '/^enable_roto_brush=/d' "$KC"
  echo "Activación quitada de kritarc (copia: $KC.backup_roto_brush)"
fi

# Sobras que delatan una instalación a medias
left=$(find "$HOME/.local/share/krita/pykrita" -maxdepth 1 -name 'roto_brush*' 2>/dev/null)
if [ -n "$left" ]; then
  echo "QUEDAN restos: $left" >&2
  exit 1
fi
echo "Desinstalado. Reinicia Krita para que desaparezca del menú."
