"""Local sentence-transformers embeddings (optional [embeddings] extra).

embed() lazy-loads all-MiniLM-L6-v2 on first use. If the extra isn't installed,
is_available() returns False and callers skip embedding (runs still succeed).
Tests monkeypatch `embed` directly, so the model is never loaded in CI.
"""

from functools import lru_cache

EMBEDDING_DIM = 384
_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer  # heavy import, lazy

    return SentenceTransformer(_MODEL_NAME)


def is_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


def embed(text: str) -> list[float]:
    """Return a normalized EMBEDDING_DIM vector. Raises if the extra is absent."""
    vec = _model().encode(text, normalize_embeddings=True)
    return vec.tolist()
