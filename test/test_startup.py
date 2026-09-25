"""Tests de arranque y validacion - Fase 7"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_config_has_no_user_paths():
    """config.yaml no debe contener rutas absolutas de usuario."""
    from jarvis_local.config import CONFIG_FILE
    if CONFIG_FILE.exists():
        content = CONFIG_FILE.read_text(encoding="utf-8")
        username = os.environ.get("USERNAME", "herna")
        if username.lower() in content.lower():
            for line in content.split("\n"):
                if ":" in line and username.lower() in line.lower() and not line.strip().startswith("#"):
                    key = line.split(":")[0].strip()
                    if key not in ("dir", "name", "language", "stt_language",
                                   "stt_compute_type", "stt_model", "tts_voice"):
                        assert False, f"Ruta absoluta de usuario en config: {line.strip()}"


def test_script_detects_root_from_anywhere():
    """Simula que run_jarvis.ps1 detecta la raiz correctamente."""
    script = Path(__file__).parent.parent / "run_jarvis.ps1"
    if script.exists():
        content = script.read_text(encoding="utf-8")
        assert '$MyInvocation.MyCommand.Path' in content
        assert 'Split-Path -Parent' in content
        assert 'Set-Location $scriptDir' in content


def test_diagnose_does_not_modify_config():
    """diagnose_jarvis.ps1 no modifica config.yaml."""
    script = Path(__file__).parent.parent / "diagnose_jarvis.ps1"
    if script.exists():
        content = script.read_text(encoding="utf-8", errors="ignore")
        assert "Set-Content" not in content
        assert "Out-File config.yaml" not in content
        assert ">> config.yaml" not in content


def test_diagnose_does_not_start_mic():
    script = Path(__file__).parent.parent / "diagnose_jarvis.ps1"
    if script.exists():
        content = script.read_text(encoding="utf-8", errors="ignore")
        assert "sd.rec" not in content
        assert "sd.play" not in content
        assert "listen()" not in content


def test_diagnose_does_not_download_models():
    script = Path(__file__).parent.parent / "diagnose_jarvis.ps1"
    if script.exists():
        content = script.read_text(encoding="utf-8", errors="ignore")
        assert "download" not in content.lower()
        assert "ollama pull" not in content.lower()
        assert "WhisperModel(" not in content


def test_python_available():
    import sys
    assert sys.version_info >= (3, 9)


def test_no_regressions_after_phase7():
    """Todas las suites existentes deben seguir importables y con API valida."""
    import jarvis_local.intent.parser as parser_mod
    import jarvis_local.jarvis as jarvis_mod
    import jarvis_local.memory_context.session as session_mod
    import jarvis_local.safety.policy as policy_mod
    import jarvis_local.storage.history as history_mod
    import jarvis_local.storage.memory as memory_mod
    import jarvis_local.voice.stt as stt_mod

    assert hasattr(parser_mod, "parse_intent")
    assert hasattr(jarvis_mod, "Jarvis")
    assert hasattr(session_mod, "SessionMemoryContext")
    assert hasattr(policy_mod, "SafetyPolicy")
    assert callable(getattr(history_mod, "HistoryStore", None))
    assert callable(getattr(memory_mod, "MemoryStore", None))
    assert callable(getattr(stt_mod, "load_voice_config", None))


if __name__ == "__main__":
    test_config_has_no_user_paths()
    test_script_detects_root_from_anywhere()
    test_diagnose_does_not_modify_config()
    test_diagnose_does_not_start_mic()
    test_diagnose_does_not_download_models()
    test_python_available()
    test_no_regressions_after_phase7()
    print("OK: Todos los tests de arranque pasaron.")
