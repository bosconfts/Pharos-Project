"""
Step 7 — Embeddings
Gera vetores semânticos com sentence-transformers (all-MiniLM-L6-v2, 384 dims).
Modelo roda localmente — sem custo de API.
"""
from __future__ import annotations
from typing import List

_model = None  # lazy load


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> List[float]:
    """Retorna embedding como lista de floats (384 dims)."""
    model = _get_model()
    vec   = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Processa múltiplos textos de uma vez (mais eficiente)."""
    model = _get_model()
    vecs  = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=True)
    return [v.tolist() for v in vecs]


if __name__ == "__main__":
    print("=== PIL M2 — Step 7: Embeddings ===\n")
    print("Carregando modelo all-MiniLM-L6-v2...")
    vec = embed_text("Cardano governance proposal to improve treasury management")
    print(f"✅ Embedding gerado: {len(vec)} dimensões")
    print(f"   Primeiros 5 valores: {[round(v, 4) for v in vec[:5]]}")
