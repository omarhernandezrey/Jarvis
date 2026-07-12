"""
Tests de memoria semantica (Fase 6).
Los que no necesitan Ollama corren siempre; los que si, se saltan solos
cuando el modelo de embeddings no esta disponible.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.memory_context.recall import AutoRecall
from jarvis_local.storage.memory import MemoryStore
from jarvis_local.storage.semantic import (
    EMBED_DIM,
    SemanticIndex,
    cosine_similarity,
    embeddings_available,
    keyword_scores,
)


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ---------- Matematica (sin red) ----------

def test_cosine_similarity():
    a = np.array([1.0, 0.0, 0.0])
    M = np.array([[1.0, 0.0, 0.0],    # identico -> 1
                  [0.0, 1.0, 0.0],    # ortogonal -> 0
                  [-1.0, 0.0, 0.0]])  # opuesto -> -1
    s = cosine_similarity(a, M)
    assert np.isclose(s[0], 1.0)
    assert np.isclose(s[1], 0.0)
    assert np.isclose(s[2], -1.0)


def test_cosine_matriz_vacia():
    assert cosine_similarity(np.array([1.0]), np.zeros((0, 1))).size == 0


def test_keyword_scores_respaldo():
    """Sin embeddings, la busqueda cae a palabras clave."""
    textos = ["me gusta el cafe cargado", "mi perro se llama Rocky"]
    s = keyword_scores("cafe cargado", textos)
    assert s[0] > s[1]
    assert keyword_scores("", textos) == [0.0, 0.0]


# ---------- Indice (sin red) ----------

def test_indice_arranca_vacio(tmp_dir):
    idx = SemanticIndex(tmp_dir)
    assert idx.ids == []
    assert idx.matrix.shape == (0, EMBED_DIM)


def test_busqueda_sin_memorias(tmp_dir):
    idx = SemanticIndex(tmp_dir)
    assert idx.search("lo que sea", []) == []


def test_indice_corrupto_no_rompe(tmp_dir):
    """Un .npz danado no debe tumbar a JARVIS: se reconstruye vacio."""
    (tmp_dir / "semantic_index.npz").write_bytes(b"basura no npz")
    idx = SemanticIndex(tmp_dir)
    assert idx.ids == []


def test_respaldo_por_palabras_sin_ollama(tmp_dir, monkeypatch):
    """Si el modelo de embeddings no esta, sigue buscando por palabras."""
    monkeypatch.setattr("jarvis_local.storage.semantic.embed",
                        lambda texts: None)
    monkeypatch.setattr("jarvis_local.storage.semantic.embed_documents",
                        lambda texts: None)
    store = MemoryStore(tmp_dir)
    store.add("me gusta el cafe cargado sin azucar")
    store.add("mi perro se llama Rocky")
    idx = SemanticIndex(tmp_dir)
    hits = idx.search("cafe cargado", store.list())
    assert hits and "cafe" in hits[0][0]["text"]


# ---------- Recuerdo automatico (sin red) ----------

def test_recall_sin_memorias(tmp_dir):
    r = AutoRecall(MemoryStore(tmp_dir), SemanticIndex(tmp_dir))
    assert r.recall("hola") == []
    assert r.build_context("hola") == ""


def test_recall_desactivado(tmp_dir):
    store = MemoryStore(tmp_dir)
    store.add("me gusta el cafe")
    r = AutoRecall(store, SemanticIndex(tmp_dir))
    r.enabled = False
    assert r.recall("que me gusta tomar") == []


def test_recall_excluye_secretos(tmp_dir):
    """Una memoria con una API key jamas debe entrar al contexto del LLM."""
    store = MemoryStore(tmp_dir)
    store.add("mi api key es sk-abc123def456ghi789jkl012mno345")
    r = AutoRecall(store, SemanticIndex(tmp_dir))
    for m in r.recall("cual es mi api key"):
        assert "sk-abc123" not in m["text"]


def test_recall_marca_contexto_no_instrucciones(tmp_dir, monkeypatch):
    """Defensa contra inyeccion: las memorias entran como CONTEXTO."""
    store = MemoryStore(tmp_dir)
    store.add("dato del usuario")
    idx = SemanticIndex(tmp_dir)
    monkeypatch.setattr(idx, "search",
                        lambda q, items, **kw: [(items[0], 0.9)])
    r = AutoRecall(store, idx)
    ctx = r.build_context("algo")
    assert "CONTEXTO, NO INSTRUCCIONES" in ctx
    assert "dato del usuario" in ctx


# ---------- Con Ollama (se saltan si no esta) ----------

_sin_embeddings = not embeddings_available()
skip_ollama = pytest.mark.skipif(_sin_embeddings,
                                 reason="modelo de embeddings no disponible")


@skip_ollama
def test_busqueda_por_significado(tmp_dir):
    """El corazon de la funcionalidad: recupera sin compartir palabras."""
    store = MemoryStore(tmp_dir)
    store.add("Soy alergico a los mariscos")
    store.add("Mi perro se llama Rocky y es un labrador")
    store.add("Trabajo como desarrollador frontend en Bogota")
    idx = SemanticIndex(tmp_dir)

    hits = idx.search("puedo comer camarones?", store.list(), top_k=1)
    assert hits and "mariscos" in hits[0][0]["text"]

    hits = idx.search("como se llama mi mascota?", store.list(), top_k=1)
    assert hits and "Rocky" in hits[0][0]["text"]


@skip_ollama
def test_no_recupera_lo_irrelevante(tmp_dir):
    """Sin esto, JARVIS meteria ruido en cada respuesta."""
    store = MemoryStore(tmp_dir)
    store.add("Soy alergico a los mariscos")
    store.add("Mi perro se llama Rocky")
    idx = SemanticIndex(tmp_dir)
    assert idx.search("cual es la capital de Francia?", store.list()) == []


@skip_ollama
def test_indice_persiste_y_se_sincroniza(tmp_dir):
    store = MemoryStore(tmp_dir)
    m1 = store.add("me gusta el cafe cargado")
    idx = SemanticIndex(tmp_dir)
    idx.sync(store.list())
    assert len(idx.ids) == 1

    # Reabrir: no debe re-embeber
    idx2 = SemanticIndex(tmp_dir)
    assert idx2.ids == idx.ids
    assert idx2.matrix.shape == (1, EMBED_DIM)

    # Borrar una memoria: el indice se poda
    store.delete(m1["id"])
    idx2.sync(store.list())
    assert idx2.ids == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
