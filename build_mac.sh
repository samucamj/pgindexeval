#!/usr/bin/env bash
# =====================================================================
#  build_mac.sh  -  gera o aplicativo pgIndexEval para macOS.
#  Execute ESTE script EM UM MAC (nao e possivel compilar para Mac a
#  partir do Windows). Requer Python 3.10+ instalado.
#
#  Uso:
#      chmod +x build_mac.sh
#      ./build_mac.sh
#  Saida:
#      dist/pgIndexEval.app   (aplicativo para dar duplo clique no Finder)
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"

echo ">> Instalando dependencias (ambiente virtual recomendado)..."
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade pyinstaller "psycopg[binary]" numpy reportlab

echo ">> Compilando o aplicativo..."
# No macOS/Linux o separador de --add-data e ':' (no Windows e ';').
python3 -m PyInstaller --noconfirm --clean --windowed --name pgIndexEval \
  --add-data "web:web" \
  --collect-all psycopg \
  --collect-all reportlab \
  pgindexeval_app.py

echo ""
echo ">> Pronto: dist/pgIndexEval.app"
echo "   Para distribuir, compacte o .app:"
echo "     cd dist && zip -r pgIndexEval-mac.zip pgIndexEval.app"
echo ""
echo "   Observacao: como o app nao e assinado/notarizado, no primeiro uso"
echo "   o Gatekeeper pode bloquear. O usuario abre com o botao direito ->"
echo "   Abrir, ou executa:  xattr -dr com.apple.quarantine pgIndexEval.app"
