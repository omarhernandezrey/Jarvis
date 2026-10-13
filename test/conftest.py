"""
Conftest para tests de JARVIS.

Configura el path una sola vez para todos los tests y -- lo mas importante --
**aisla al usuario de sus propios tests**.

Antes esto no existia y correr la suite mutaba datos REALES:
  * escribia en `data/history.json` de verdad, y como el historial se recorta
    a N mensajes, la basura de los tests expulsaba conversaciones reales;
  * ensuciaba `logs/audit.jsonl` y `logs/trace.jsonl`, que son los ficheros que
    consultan `jarvis doctor` y `trace_query`;
  * borraba el token de Spotify cacheado (`data/.spotify_cache`), asi que habia
    que reautorizar la cuenta despues de cada corrida;
  * creaba ficheros en `~/Documentos` y `~/Escritorio` (`user_dir()`).

Todo eso ahora apunta a un sandbox temporal que se fija ANTES de importar
`jarvis_local` (muchos modulos calculan rutas al importarse). La configuracion
y los secrets siguen leyendose del proyecto: lo que se aísla es lo que JARVIS
ESCRIBE, no el codigo ni las credenciales.
"""
import os
import sys
import tempfile
from pathlib import Path

# Añadir el directorio raíz al path para imports
_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))

# ── Qt: UNA sola QApplication para todo el proceso (fusionado desde
# jarvis_hud_pro/tests/conftest.py) ─────────────────────────────────────
# test_ui_hud.py crea una QGuiApplication al importarse (nivel de módulo,
# antes de cualquier fixture); los tests del HUD pro (test_hud_pro.py,
# test_adapter.py) usan QtWidgets y necesitan una QApplication real. Si el
# singleton ya existe como QGuiApplication "a secas" cuando se intenta crear
# el primer QWidget, Qt aborta el PROCESO ENTERO (SIGABRT, no una excepción
# Python) — verificado en esta máquina, no es una hipótesis. Crear la
# QApplication aquí, en el conftest (que pytest siempre importa antes que
# cualquier módulo de test del directorio), garantiza que sea siempre la
# primera: QApplication YA ES una QGuiApplication, así que el
# `QGuiApplication.instance() or QGuiApplication([])` de test_ui_hud.py
# simplemente la reutiliza sin problema en el sentido contrario.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

_QAPP = QApplication.instance() or QApplication([])

# ── SANDBOX ──────────────────────────────────────────────────────────────
# Se crea en cuanto se importa el conftest (antes que cualquier test) y NO se
# borra al terminar: así, si algo se sigue escapando, queda visible en /tmp.
_SANDBOX = Path(tempfile.mkdtemp(prefix="jarvis-tests-"))
(_SANDBOX / "data").mkdir(parents=True, exist_ok=True)
(_SANDBOX / "logs").mkdir(parents=True, exist_ok=True)
os.environ["JARVIS_BASE_DIR"] = str(_SANDBOX)

# Carpetas del usuario (Documentos, Escritorio...) dentro del sandbox:
# `xdg-user-dir` consulta `$XDG_CONFIG_HOME/user-dirs.dirs`, asi que
# `config.user_dir()` deja de tocar la casa del usuario. No se toca HOME: si se
# cambiara, tambien cambiaria la cache de modelos (HuggingFace) y los tests
# de voz volverian a descargar Whisper.
_HOME_FALSA = _SANDBOX / "home"
_XDG = _SANDBOX / "xdg"
_XDG.mkdir(parents=True, exist_ok=True)
_CLAVES = ("DESKTOP", "DOWNLOAD", "DOCUMENTS", "MUSIC", "PICTURES", "VIDEOS")
for _clave in _CLAVES:
    (_HOME_FALSA / _clave.capitalize()).mkdir(parents=True, exist_ok=True)
(_XDG / "user-dirs.dirs").write_text(
    "\n".join(f'XDG_{c}_DIR="{_HOME_FALSA / c.capitalize()}"' for c in _CLAVES) + "\n",
    encoding="utf-8",
)
os.environ["XDG_CONFIG_HOME"] = str(_XDG)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _limpiar_cache_decisiones():
    """La cache de decisiones del agente (C6) es estado global de modulo: se
    vacia antes y despues de CADA test para que uno no herede la decision de
    otro (romperia asserts de call_count del cliente mock)."""
    try:
        from jarvis_local.agent import decision_cache
        decision_cache.clear()
        yield
        decision_cache.clear()
    except Exception:
        yield


@pytest.fixture
def sandbox() -> Path:
    """BASE_DIR de esta corrida de tests (datos y logs temporales)."""
    return _SANDBOX


@pytest.fixture
def home_dir() -> Path:
    """Sustituto de la carpeta personal (Documentos/Escritorio incluidos)."""
    return _HOME_FALSA


@pytest.fixture(scope="session")
def qapp():
    """La QApplication única del proceso (ver el bloque Qt arriba)."""
    return _QAPP


@pytest.fixture
def jarvis_mock():
    """Fixture que proporciona Jarvis con cliente mockeado."""
    from unittest.mock import MagicMock

    from jarvis_local.jarvis import Jarvis
    j = Jarvis()
    mc = MagicMock()
    mc.is_running = MagicMock(return_value=True)
    mc.model_exists = MagicMock(return_value=True)
    mc.chat = MagicMock(return_value=iter([]))
    j.client = mc
    return j, mc
