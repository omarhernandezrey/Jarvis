# JARVIS Local - Script de instalación para Windows
# Ejecutar en PowerShell como administrador

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  JARVIS Local - Instalador para Windows" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python no encontrado." -ForegroundColor Red
    Write-Host "Por favor instale Python 3.11+ desde https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Asegurese de marcar 'Add Python to PATH' durante la instalación." -ForegroundColor Yellow
    exit 1
}

# Crear entorno virtual
Write-Host "[1/5] Creando entorno virtual..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

# Activar entorno virtual
Write-Host "[2/5] Activando entorno virtual..." -ForegroundColor Yellow
. .\.venv\Scripts\Activate.ps1

# Instalar dependencias
Write-Host "[3/5] Instalando dependencias..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt

# Verificar Ollama
Write-Host "[4/5] Verificando Ollama..." -ForegroundColor Yellow
try {
    ollama --version | Out-Null
    Write-Host "[OK] Ollama encontrado" -ForegroundColor Green
} catch {
    Write-Host "[INFO] Ollama no encontrado." -ForegroundColor Yellow
    Write-Host "Descargue Ollama desde https://ollama.com/download" -ForegroundColor Yellow
    Write-Host "Después de instalar, ejecute: ollama pull qwen2.5:3b" -ForegroundColor Yellow
}

# Descargar modelos
Write-Host "[5/5] Descargando modelos..." -ForegroundColor Yellow
try {
    ollama pull qwen2.5:3b
    Write-Host "[OK] qwen2.5:3b descargado" -ForegroundColor Green
} catch {
    Write-Host "[WARN] No se pudo descargar qwen2.5:3b" -ForegroundColor Yellow
}

try {
    ollama pull bge-m3
    Write-Host "[OK] bge-m3 descargado" -ForegroundColor Green
} catch {
    Write-Host "[WARN] No se pudo descargar bge-m3 (opcional)" -ForegroundColor Yellow
}

# Verificar instalación
Write-Host "Verificando instalación..." -ForegroundColor Yellow
python -c "import jarvis_local; print('[OK] jarvis_local importado correctamente')"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Instalación completada" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para ejecutar JARVIS:" -ForegroundColor White
Write-Host "  .venv\Scripts\activate" -ForegroundColor Gray
Write-Host "  python -m jarvis_local.cli" -ForegroundColor Gray
Write-Host ""
Write-Host "Para ejecutar tests:" -ForegroundColor White
Write-Host "  python -m pytest test -q" -ForegroundColor Gray
Write-Host ""
