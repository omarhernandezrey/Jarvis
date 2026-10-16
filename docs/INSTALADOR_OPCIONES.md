# Opciones de empaquetado — JARVIS Local

Comparación de las tres opciones consideradas para reducir la fricción de
instalación en Linux (Ubuntu/Debian). El README actual § "📦 Instalación"
documenta 4–5 pasos manuales: clonar, `sudo apt install` de dependencias
del SO (xclip, playerctl, libportaudio2, python3-venv, python3-tk,
python3-gi), instalación de Ollama por fuera, venv con `--system-site-packages`,
`pip install -r requirements.txt` y descarga de modelos (`llama3.2:3b`,
`bge-m3`, opcionalmente `qwen2.5:3b`).

## Opción 1 — Script de instalación guiado (`install.sh`)

- Resuelve: creación del venv, dependencias de Python, detección de
  dependencias del SO faltantes (Tkinter, PortAudio, PipeWire), detección de
  Ollama y descarga de modelos, con mensajes de error accionables.
- No resuelve: las dependencias del SO ni Ollama las instala por sí mismo —
  las delega al usuario (script imprime el `apt install`/instrucciones exactas,
  nunca ejecuta sudo).
- Esfuerzo de implementación: medio. Mantenimiento: medio — debe seguir
  `requirements.txt` cuando cambie.
- Limitaciones: depende de la guía del usuario para sudo; no enlaza binario a
  PATH. Funciona siempre que el entorno sea similar al documentado.

## Opción 2 — Paquete `.deb` (Debian/Ubuntu)

- Resuelve: instalación a nivel de SO vía apt, metadatos de dependencias.
- No resuelve: Ollama (no está en apt oficial) ni el venv Python; las
  dependencias Python del repo son las que cambian más rápido.
- Esfuerzo de implementación: alto. Mantenimiento: alto — firmado, repositorio,
  versionado en lockstep con requirements, gestión de conflictos con PySide6.
- Limitaciones: sobrecarga de empaquetado que no aborda el problema real
  (pasos manuales de hoy) para un proyecto con un solo mantenedor en
  desarrollo activo.

## Opción 3 — `Makefile`/script simple (`make install`, `make run`)

- Resuelve: encapsular los comandos manuales en un único comando; bajo costo.
- No resuelve: detección ni instalación de dependencias del SO; si falta algo,
  falla igual que el procedimiento manual.
- Esfuerzo de implementación: bajo. Mantenimiento: bajo.
- Limitaciones: frágil ante entornos no probados; no guía al usuario que falta.

## Precedentes verificables

No se identificó un precedente documentado en este repositorio ni en los
precedentes del plan (`IMPLEMENTACION_DE_MEJORAS.md`, `PLAN_MAESTRO.md`,
`docs/PLAN_EJECUCION.md`) que cite un proyecto comparable con una u otra
opción. Cualquier afirmación externa de precedente se dejaría sin sustento,
por eso no se inventa uno.

## Decisión ya tomada

Se implementa un script guiado (`install.sh`) combinado con un `Makefile`
envolvente (Tareas 3.1 y 3.2 de este plan). Se descarta el `.deb` por el
sobrecosto de mantenimiento de empaquetado nativo que no resuelve el
problema real —los pasos manuales de hoy— frente a un proyecto de desarrollo
activo con un solo mantenedor. El `Makefile` queda como entrada de uso
cotidiano (`make install`, `make run`, `make test`, `make lint`, `make clean`).
