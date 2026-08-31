"""JARVIS — nueva capa de vista (PySide6 + Qt Quick).

Sustituye la GUI Tkinter (`jarvis_local/ui/desktop.py`). El núcleo
(STT/TTS, cliente Ollama, memoria, tools, config) no se toca: la vista
habla con él a través de un ViewModel/bus de eventos y nunca bloquea su
hilo (ver `jarvis_local/ui/hud/viewmodel.py`).
"""
from jarvis_local.ui.hud.app import main

__all__ = ["main"]
