"""
JARVIS Local - Memoria semantica (Fase 6)

Busca en las memorias por SIGNIFICADO, no por texto exacto: "que me gusta
tomar?" encuentra "prefiero el cafe sin azucar" aunque no compartan palabras.

Usa embeddings locales (nomic-embed-text via Ollama, 768 dimensiones) y
similitud coseno en NumPy. Sin base de datos vectorial: con cientos de
memorias, un producto punto sobre una matriz pequena es instantaneo y
ahorra una dependencia pesada (ChromaDB/FAISS) en un equipo modesto.

Degradacion: si Ollama o el modelo de embeddings no estan, cae a busqueda por
palabras. La funcionalidad se reduce, no se rompe.
"""
import json
from pathlib import Path

import numpy as np
import requests

from jarvis_local.config import get_config

# bge-m3, no nomic-embed-text: nomic es un modelo de ingles y en espanol no
# discrimina. Medido con 6 memorias y 6 preguntas reales de este proyecto
# (bench en el equipo del usuario):
#
#   modelo                     aciertos   margen      falso positivo
#   nomic-embed-text             5/6      +0.028          0.52
#   nomic + prefijos de tarea    4/6      +0.013          0.55
#   bge-m3 (multilingue)         5/6      +0.124          0.33
#
# El margen (distancia entre la memoria correcta y la siguiente) es lo que
# permite poner un umbral util: con nomic todo puntuaba ~0.55 y no se podia
# separar lo relevante del ruido. bge-m3 no usa prefijos de tarea.
EMBED_MODEL = "bge-m3"
EMBED_DIM = 1024
_TIMEOUT = 120


def _host() -> str:
    return get_config()["ollama"]["host"]


def embed(texts: list[str]) -> list[list[float]] | None:
    """Vectores de los textos. None si el modelo de embeddings no esta."""
    if not texts:
        return []
    try:
        r = requests.post(f"{_host()}/api/embed",
                          json={"model": EMBED_MODEL, "input": texts},
                          timeout=_TIMEOUT)
        r.raise_for_status()
        vectores = r.json().get("embeddings", [])
        return vectores if len(vectores) == len(texts) else None
    except (requests.RequestException, KeyError, ValueError):
        return None


def embed_documents(texts: list[str]) -> list[list[float]] | None:
    return embed(texts)


def embed_query(text: str) -> list[float] | None:
    v = embed([text])
    return v[0] if v else None


def embeddings_available() -> bool:
    return embed(["ping"]) is not None


def cosine_similarity(a: np.ndarray, matriz: np.ndarray) -> np.ndarray:
    """Similitud coseno de un vector contra cada fila de la matriz."""
    if matriz.size == 0:
        return np.array([])
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    m_norm = matriz / (np.linalg.norm(matriz, axis=1, keepdims=True) + 1e-10)
    return m_norm @ a_norm


def _palabras(texto: str) -> set[str]:
    return {w for w in texto.lower().split() if len(w) > 3}


def keyword_scores(query: str, textos: list[str]) -> list[float]:
    """Respaldo sin embeddings: solapamiento de palabras (Jaccard simple)."""
    q = _palabras(query)
    if not q:
        return [0.0] * len(textos)
    out = []
    for t in textos:
        p = _palabras(t)
        out.append(len(q & p) / len(q | p) if p else 0.0)
    return out


class SemanticIndex:
    """Indice de vectores persistido junto a las memorias.

    Se guarda como .npz (matriz + ids). Si una memoria se agrega o borra, el
    indice se reconstruye solo para lo que falta: no re-embebe todo.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.data_dir / "semantic_index.npz"
        self.ids: list[str] = []
        self.matrix: np.ndarray = np.zeros((0, EMBED_DIM), dtype=np.float32)
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = np.load(self._path, allow_pickle=False)
            self.matrix = data["matrix"].astype(np.float32)
            self.ids = json.loads(str(data["ids"]))
            if len(self.ids) != self.matrix.shape[0]:  # indice inconsistente
                self.ids, self.matrix = [], np.zeros((0, EMBED_DIM), np.float32)
        except Exception:
            self.ids, self.matrix = [], np.zeros((0, EMBED_DIM), np.float32)

    def _save(self):
        np.savez_compressed(self._path, matrix=self.matrix,
                            ids=np.array(json.dumps(self.ids)))

    def sync(self, items: list[dict]) -> bool:
        """Alinea el indice con las memorias. True si uso embeddings."""
        actuales = {it["id"]: it["text"] for it in items}
        nuevos = [i for i in actuales if i not in self.ids]
        borrados = [i for i in self.ids if i not in actuales]

        if not nuevos and not borrados:
            return self.matrix.shape[0] == len(actuales)

        if borrados:
            keep = [k for k, i in enumerate(self.ids) if i not in borrados]
            self.matrix = self.matrix[keep] if keep else \
                np.zeros((0, EMBED_DIM), np.float32)
            self.ids = [self.ids[k] for k in keep]

        if nuevos:
            vectores = embed_documents([actuales[i] for i in nuevos])
            if vectores is None:
                return False  # sin embeddings: el caller usara palabras clave
            nueva = np.array(vectores, dtype=np.float32)
            self.matrix = (nueva if self.matrix.size == 0
                           else np.vstack([self.matrix, nueva]))
            self.ids.extend(nuevos)

        self._save()
        return True

    def search(self, query: str, items: list[dict], top_k: int = 3,
               min_score: float = 0.45) -> list[tuple[dict, float]]:
        """Memorias mas parecidas a la consulta, con su puntaje (0-1)."""
        if not items:
            return []
        por_id = {it["id"]: it for it in items}

        usa_vectores = self.sync(items)
        if usa_vectores and self.matrix.size:
            q = embed_query(query)
            if q:
                scores = cosine_similarity(np.array(q, dtype=np.float32),
                                           self.matrix)
                pares = [(por_id[i], float(s))
                         for i, s in zip(self.ids, scores, strict=False)
                         if i in por_id]
                pares.sort(key=lambda x: -x[1])
                return [(m, s) for m, s in pares[:top_k] if s >= min_score]

        # Respaldo: palabras clave (umbral mas bajo, la metrica es mas pobre)
        textos = [it["text"] for it in items]
        scores = keyword_scores(query, textos)
        pares = sorted(zip(items, scores, strict=False), key=lambda x: -x[1])
        return [(m, s) for m, s in pares[:top_k] if s >= 0.15]

    def clear(self):
        self.ids = []
        self.matrix = np.zeros((0, EMBED_DIM), dtype=np.float32)
        if self._path.exists():
            self._path.unlink()
