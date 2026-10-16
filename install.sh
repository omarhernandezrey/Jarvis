#!/bin/bash
# JARVIS Local - Script de instalación guiado para Linux (Ubuntu/Debian)
# Uso: ./install.sh
#
# No instala paquetes de sistema ni Ollama por su cuenta: si falta algo,
# imprime el comando exacto y sale con código distinto de cero. Instalar
# dependencias de sistema o Ollama es una decisión del usuario final, no
# de este script.

set -euo pipefail

echo "=========================================="
echo "  JARVIS Local - Instalador guiado (Linux)"
echo "=========================================="

# 1. Version de Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 no encontrado en PATH. Instala Python 3.11 o superior."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; then
    echo "[ERROR] Se requiere Python 3.11+, encontrado $PYTHON_VERSION."
    exit 1
fi
echo "[OK] Python $PYTHON_VERSION"

# 2. Entorno virtual
if [ ! -d ".venv" ]; then
    echo "[1/6] Creando entorno virtual (.venv)..."
    python3 -m venv --system-site-packages .venv
else
    echo "[1/6] .venv ya existe, se reutiliza."
fi

# 3. Dependencias de Python
echo "[2/6] Instalando dependencias de Python (requirements.txt)..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 4. Dependencias de sistema (Tkinter, PortAudio, PipeWire y utilitarios de
#    escritorio) - solo se detectan, nunca se instalan automaticamente.
echo "[3/6] Verificando dependencias de sistema..."
MISSING_SYSTEM_DEPS=0

if ! .venv/bin/python3 -c "import tkinter" &> /dev/null; then
    echo "[FALTA] Tkinter no disponible para este Python."
    MISSING_SYSTEM_DEPS=1
fi

if ! pkg-config --exists libportaudio2 2>/dev/null && ! ldconfig -p 2>/dev/null | grep -q libportaudio; then
    echo "[FALTA] PortAudio (libportaudio2) no encontrado."
    MISSING_SYSTEM_DEPS=1
fi

if ! command -v pactl &> /dev/null && ! command -v pw-cli &> /dev/null; then
    echo "[FALTA] PipeWire/PulseAudio (pactl o pw-cli) no encontrado."
    MISSING_SYSTEM_DEPS=1
fi

if [ "$MISSING_SYSTEM_DEPS" -ne 0 ]; then
    echo ""
    echo "[ERROR] Faltan dependencias de sistema. Instalalas con:"
    echo "  sudo apt install -y xclip playerctl libportaudio2 python3-venv python3-tk python3-gi gir1.2-glib-2.0"
    echo ""
    echo "Este script NO ejecuta sudo/apt por tu cuenta. Corre el comando de"
    echo "arriba y vuelve a ejecutar ./install.sh."
    exit 1
fi
echo "[OK] Dependencias de sistema detectadas."

# 5. Ollama
echo "[4/6] Verificando Ollama..."
if ! command -v ollama &> /dev/null; then
    echo ""
    echo "[ERROR] Ollama no encontrado en PATH. Instalalo con:"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    echo "Este script NO instala Ollama por tu cuenta. Corre el comando de"
    echo "arriba y vuelve a ejecutar ./install.sh."
    exit 1
fi
echo "[OK] Ollama encontrado."

# 6. Modelos (best-effort: si falla, se avisa pero no se aborta el script)
echo "[5/6] Descargando modelos de Ollama (llama3.2:3b, bge-m3)..."
ollama pull llama3.2:3b || echo "[WARN] No se pudo descargar llama3.2:3b (puedes bajarlo despues)"
ollama pull bge-m3 || echo "[WARN] No se pudo descargar bge-m3 (puedes bajarlo despues)"

echo "[6/6] Instalación completada."
echo ""
echo "=========================================="
echo "  JARVIS Local listo"
echo "=========================================="
echo ""
echo "Para arrancar JARVIS:"
echo "  .venv/bin/python -m jarvis_local.cli"
echo ""
echo "(si tu shell no tiene activo .venv, actívalo primero con"
echo " 'source .venv/bin/activate' o usa la ruta completa de arriba)"
