"""PLAN_EJECUCION FASE E · E0 — presupuesto de memoria.

Sin psutil: se parchea `_MEMINFO` a un fichero de prueba y se comprueban los
umbrales, el aviso de swap y la descarga de bge-m3.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.agent import memory_guard as mg

_HOLGADA = "MemTotal: 16000000 kB\nMemAvailable: 6000000 kB\nSwapTotal: 4000000 kB\nSwapFree: 4000000 kB\n"
_AJUSTADA = "MemTotal: 16000000 kB\nMemAvailable: 500000 kB\nSwapTotal: 4000000 kB\nSwapFree: 3950000 kB\n"
_EN_SWAP = "MemTotal: 16000000 kB\nMemAvailable: 400000 kB\nSwapTotal: 4000000 kB\nSwapFree: 2500000 kB\n"
# swap OCUPADO pero RAM holgada: páginas frías de una sesión pesada anterior.
# NO es degradación — el turno no va a paginar. (Caso real observado en vivo.)
_SWAP_FRIO = "MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\nSwapTotal: 4000000 kB\nSwapFree: 300000 kB\n"


def _meminfo(tmp_path, contenido: str) -> str:
    p = tmp_path / "meminfo"
    p.write_text(contenido, encoding="ascii")
    return str(p)


def test_snapshot_holgada(tmp_path):
    with patch.object(mg, "_MEMINFO", _meminfo(tmp_path, _HOLGADA)):
        s = mg.snapshot()
    assert s["disponible"] and not s["ajustado"] and not s["en_swap"]
    assert s["mem_available_kb"] == 6_000_000
    assert s["swap_usado_kb"] == 0


def test_snapshot_ajustada_pero_sin_swap(tmp_path):
    with patch.object(mg, "_MEMINFO", _meminfo(tmp_path, _AJUSTADA)):
        s = mg.snapshot()
        assert mg.ajustado() is True
        assert mg.en_swap() is False        # 50 MB de swap, bajo el umbral
    assert s["ajustado"] and not s["en_swap"]


def test_snapshot_en_swap_degradado(tmp_path):
    with patch.object(mg, "_MEMINFO", _meminfo(tmp_path, _EN_SWAP)):
        assert mg.ajustado() is True
        assert mg.en_swap() is True          # 1,5 GB de swap usados
        assert mg.degradado() is True        # + poca RAM -> va a paginar
        aviso = mg.aviso_degradado()
    assert aviso and "swap" in aviso.lower() and "MB disponibles" in aviso


def test_swap_ocupado_pero_ram_holgada_no_es_degradacion(tmp_path):
    with patch.object(mg, "_MEMINFO", _meminfo(tmp_path, _SWAP_FRIO)):
        assert mg.en_swap() is True          # hay 3,7 GB en swap
        assert mg.degradado() is False       # pero 8 GB de RAM libre: frías
        assert mg.aviso_degradado() is None
        assert "páginas frías" in mg.linea_estado()


def test_sin_proc_meminfo_todo_noop(tmp_path):
    with patch.object(mg, "_MEMINFO", str(tmp_path / "no_existe")):
        assert mg.snapshot() == {"disponible": False}
        assert mg.ajustado() is False
        assert mg.en_swap() is False
        assert mg.aviso_degradado() is None
        assert "no medible" in mg.linea_estado()


def test_aviso_solo_con_swap(tmp_path):
    with patch.object(mg, "_MEMINFO", _meminfo(tmp_path, _AJUSTADA)):
        assert mg.aviso_degradado() is None   # ajustada pero no en swap
    with patch.object(mg, "_MEMINFO", _meminfo(tmp_path, _HOLGADA)):
        assert mg.aviso_degradado() is None


def test_linea_estado_cuatro_estados(tmp_path):
    for contenido, marca in ((_HOLGADA, "holgada"), (_AJUSTADA, "ajustada"),
                             (_SWAP_FRIO, "frías"), (_EN_SWAP, "DEGRADADO")):
        with patch.object(mg, "_MEMINFO", _meminfo(tmp_path, contenido)):
            assert marca in mg.linea_estado()


def test_soltar_embeddings_pide_keep_alive_0():
    captura = {}

    def _post(url, json=None, timeout=None):
        captura["url"] = url
        captura["json"] = json
        return MagicMock(status_code=200)

    with patch("requests.post", side_effect=_post):
        assert mg.soltar_embeddings() is True
    assert captura["url"].endswith("/api/embed")
    assert captura["json"]["keep_alive"] == 0
    assert captura["json"]["model"]  # bge-m3


def test_soltar_embeddings_no_revienta_si_falla():
    with patch("requests.post", side_effect=OSError("Ollama caído")):
        assert mg.soltar_embeddings() is False


# --- integración: el bucle suelta bge-m3 cuando la RAM está ajustada ---------


def test_run_simple_suelta_bge_si_ajustado(monkeypatch):
    from jarvis_local.agent import loop as agent_loop

    llamado = {"soltar": 0}
    monkeypatch.setattr(agent_loop, "select_tools", lambda *a, **k: [])
    monkeypatch.setattr(agent_loop, "confidence", lambda *a, **k: 0.5)
    monkeypatch.setattr(mg, "ajustado", lambda: True)
    monkeypatch.setattr(mg, "soltar_embeddings",
                        lambda: llamado.__setitem__("soltar", llamado["soltar"] + 1) or True)

    agent_loop.run_agent(MagicMock(), "una peticion cualquiera larga y clara")
    assert llamado["soltar"] == 1


def test_run_simple_no_suelta_bge_si_holgado(monkeypatch):
    from jarvis_local.agent import loop as agent_loop

    llamado = {"soltar": 0}
    monkeypatch.setattr(agent_loop, "select_tools", lambda *a, **k: [])
    monkeypatch.setattr(agent_loop, "confidence", lambda *a, **k: 0.5)
    monkeypatch.setattr(mg, "ajustado", lambda: False)
    monkeypatch.setattr(mg, "soltar_embeddings",
                        lambda: llamado.__setitem__("soltar", llamado["soltar"] + 1) or True)

    agent_loop.run_agent(MagicMock(), "otra peticion cualquiera larga y clara")
    assert llamado["soltar"] == 0


# --- integración: JARVIS antepone el aviso cuando hay swap ------------------


def test_try_agent_antepone_el_aviso_en_swap():
    from jarvis_local.agent.loop import AgentResult
    from jarvis_local.jarvis import _mc_test

    j, _ = _mc_test()
    j.agent_enabled = True

    fake = AgentResult(text="Chrome abierto correctamente.", tools_used=["abrir_aplicacion"])
    with patch("jarvis_local.agent.loop.run_agent", return_value=fake), \
         patch.object(mg, "aviso_degradado",
                      return_value="Voy a ir lento, senor: ... swap."):
        out = j._try_agent("abre chrome", "abre chrome")

    assert out.startswith("Voy a ir lento")
    assert "Chrome abierto correctamente." in out


if __name__ == "__main__":
    print("usa pytest")
