# JARVIS Local - Script de instalación guiado para Windows
#
# AVISO IMPORTANTE: este script se escribió por analogía exacta con
# install.sh (el instalador de Linux, ya probado en uso real) y a partir de
# los pasos manuales documentados en README.md Seccion "Instalacion" ->
# "Windows". NO se ha podido ejecutar ni probar en una maquina Windows real
# durante su creacion -- el entorno de desarrollo donde se escribio es
# Linux, sin maquina Windows ni interprete de PowerShell disponibles para
# validarlo. Si falla en tu maquina, por favor abre un issue describiendo
# el error exacto.
#
# Uso: .\install.ps1

$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "  JARVIS Local - Instalador guiado (Windows)"
Write-Host "=========================================="

# 1. Version de Python
try {
    $pythonVersionRaw = (python --version) 2>&1
} catch {
    Write-Host "[ERROR] python no encontrado en PATH. Instala Python 3.11+ desde https://www.python.org/downloads/"
    exit 1
}

if ($pythonVersionRaw -match "(\d+)\.(\d+)\.(\d+)") {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
} else {
    Write-Host "[ERROR] No se pudo determinar la version de Python a partir de: $pythonVersionRaw"
    exit 1
}

if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
    Write-Host "[ERROR] Se requiere Python 3.11+, encontrado $pythonVersionRaw."
    exit 1
}
Write-Host "[OK] $pythonVersionRaw"

# 2. Entorno virtual
if (-not (Test-Path ".venv")) {
    Write-Host "[1/5] Creando entorno virtual (.venv)..."
    python -m venv .venv
} else {
    Write-Host "[1/5] .venv ya existe, se reutiliza."
}

$venvPython = ".\.venv\Scripts\python.exe"
$venvPip = ".\.venv\Scripts\pip.exe"

# 3. Dependencias de Python (ruta explicita del venv, no depende de que la
#    sesion actual lo tenga "activado")
Write-Host "[2/5] Instalando dependencias de Python (requirements.txt)..."
& $venvPip install --upgrade pip
& $venvPip install -r requirements.txt

# 4. Ollama
Write-Host "[3/5] Verificando Ollama..."
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host ""
    Write-Host "[ERROR] Ollama no encontrado en PATH. Descargalo desde:"
    Write-Host "  https://ollama.com/download"
    Write-Host ""
    Write-Host "Este script NO instala Ollama por su cuenta. Instalalo y vuelve a"
    Write-Host "ejecutar .\install.ps1."
    exit 1
}
Write-Host "[OK] Ollama encontrado."

# 5. Modelos (best-effort: si falla, se avisa pero no se aborta el script)
Write-Host "[4/5] Descargando modelos de Ollama (llama3.2:3b, bge-m3)..."
try {
    ollama pull llama3.2:3b
} catch {
    Write-Host "[WARN] No se pudo descargar llama3.2:3b (puedes bajarlo despues)"
}
try {
    ollama pull bge-m3
} catch {
    Write-Host "[WARN] No se pudo descargar bge-m3 (puedes bajarlo despues)"
}

Write-Host "[5/5] Instalacion completada."
Write-Host ""
Write-Host "=========================================="
Write-Host "  JARVIS Local listo"
Write-Host "=========================================="
Write-Host ""
Write-Host "Para arrancar JARVIS:"
Write-Host '  $env:PYTHONIOENCODING = "utf-8"'
Write-Host "  .\.venv\Scripts\python.exe -m jarvis_local.cli"
