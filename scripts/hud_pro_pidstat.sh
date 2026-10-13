#!/usr/bin/env bash
# FASE D · tarea A3 — mediciones pidstat 60s x3 de `python -m hud_pro`
# en reposo (sin --demo), para comparar el coste de CPU antes/después del
# fix de repintado-solo-al-cambiar (tarea A2, commit edf9f9b).
#
# Uso:
#   scripts/hud_pro_pidstat.sh <etiqueta> <directorio_del_código> <archivo_salida>
#
# Ejemplos (comparación antes/después real, cada condición en su propio
# worktree o checkout):
#   scripts/hud_pro_pidstat.sh antes   /ruta/al/commit/previo   antes.out
#   scripts/hud_pro_pidstat.sh despues /home/omar/Documentos/Jarvis despues.out
#
# LÍMITE CONOCIDO, documentado tras correrlo (ver A3 en el historial de
# commits): en reposo puro, el único disparador periódico es el timer de
# 2s de `TopBar._refresh` (reloj + CPU/RAM); el label de CPU/RAM cambia casi
# siempre (dato real de psutil), así que sigue forzando el repintado de la
# ventana completa con o sin el fix — el efecto medido aquí es pequeño
# (~0.3 p.p. en esta máquina). El ahorro grande de A2 (ServiceChip/
# TopBar.update_metrics descartando el MISMO estado repetido en cada
# muestreo real del backend) no se ejercita sin un bridge real conectado;
# para ESO la evidencia fiable es el conteo de repaints de
# `test/test_hud_pro_panels.py` (PaintStatsFilter), no esta medición de CPU.
set -u
LABEL="$1"
WORKDIR="$2"
OUT="$3"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/.venv/bin/python"

: > "$OUT"
for run in 1 2 3; do
    echo "=== $LABEL run $run ===" >> "$OUT"
    ( cd "$WORKDIR" && "$PY" -m hud_pro --no-console ) &
    PID=$!
    sleep 3   # estabilización: ventana creada, primeros paints hechos
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "PROCESO MURIÓ ANTES DE MEDIR (run $run)" >> "$OUT"
        continue
    fi
    pidstat -p "$PID" 1 60 >> "$OUT" 2>&1
    kill "$PID" 2>/dev/null
    wait "$PID" 2>/dev/null
    sleep 1
done
echo "=== fin $LABEL ===" >> "$OUT"
