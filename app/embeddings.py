"""Local sentence-transformers embeddings (optional [embeddings] extra).

embed() lazy-loads all-MiniLM-L6-v2 on first use. If the extra isn't installed,
is_available() returns False and callers skip embedding (runs still succeed).
Tests monkeypatch `embed` directly, so the model is never loaded in CI.
"""

from functools import lru_cache

EMBEDDING_DIM = 384
_MODEL_NAME = "all-MiniLM-L6-v2"

# Keys that carry no root-cause signal — embedding them drips commit hashes, JSON
# scaffolding and long evidence dumps into the vector (and MiniLM truncates at
# ~256 tokens), collapsing unrelated failures together. Dropped before embedding.
_NOISE_KEYS = frozenset(
    {"commit", "evidence_tail", "verdict", "token_count", "agent_model", "agent_session_id"}
)


def embed_text_for(reasoning: dict | None, notes: str | None = None) -> str:
    """Build the text to embed from a reasoning dict + notes.

    We embed the human root-cause prose, NOT ``json.dumps(reasoning)``. The raw
    dump's noise (commit hashes, keys, evidence tails) dominates similarity and
    makes genuinely-unrelated failures look close. Keep string values (e.g.
    ``root_cause``, ``method``); drop known-noise keys and non-string values.
    """
    parts: list[str] = []
    if notes and notes.strip():
        parts.append(notes.strip())
    if isinstance(reasoning, dict):
        for key, value in reasoning.items():
            if key in _NOISE_KEYS:
                continue
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
    return " ".join(parts).strip()


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
