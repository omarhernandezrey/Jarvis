#!/bin/bash
# JARVIS Local - Script de instalación para Linux (Ubuntu/Debian)
# Uso: chmod +x install.sh && ./install.sh

set -e

echo "=========================================="
echo "  JARVIS Local - Instalador para Linux"
echo "=========================================="

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 no encontrado. Instalando..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "[OK] Python encontrado: $PYTHON_VERSION"

# Verificar pip
if ! command -v pip3 &> /dev/null; then
    echo "[ERROR] pip3 no encontrado. Instalando..."
    sudo apt install -y python3-pip
fi

# Instalar dependencias del sistema
echo "[1/6] Instalando dependencias del sistema..."
sudo apt update
sudo apt install -y \
    xclip \
    playerctl \
    libportaudio2 \
    python3-venv \
    python3-tk \
    python3-gi \
    gir1.2-glib-2.0

# Crear entorno virtual
echo "[2/6] Creando entorno virtual..."
if [ ! -d ".venv" ]; then
    python3 -m venv --system-site-packages .venv
fi

# Activar entorno virtual
source .venv/bin/activate

# Instalar dependencias de Python
echo "[3/6] Instalando dependencias de Python..."
pip install --upgrade pip
pip install -r requirements.txt

# Verificar Ollama
echo "[4/6] Verificando Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "[INFO] Ollama no encontrado. Instalando..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Descargar modelos
echo "[5/6] Descargando modelos de Ollama..."
ollama pull qwen2.5:3b || echo "[WARN] No se pudo descargar qwen2.5:3b"
ollama pull bge-m3 || echo "[WARN] No se pudo descargar bge-m3 (opcional)"

# Verificar instalación
echo "[6/6] Verificando instalación..."
python3 -c "import jarvis_local; print('[OK] jarvis_local importado correctamente')"

echo ""
echo "=========================================="
echo "  Instalación completada"
echo "=========================================="
echo ""
echo "Para ejecutar JARVIS:"
echo "  .venv/bin/python -m jarvis_local.cli"
echo ""
echo "Para ejecutar tests:"
echo "  .venv/bin/python -m pytest test -q"
echo ""
echo "Para activar el entorno virtual:"
echo "  source .venv/bin/activate"
echo ""
