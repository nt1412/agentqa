import pytest

from app import embeddings
from tests._embed_helpers import fake_embed


def test_fake_embed_is_deterministic_and_dim():
    a = fake_embed("login failed")
    b = fake_embed("login failed")
    c = fake_embed("payment failed")
    assert len(a) == embeddings.EMBEDDING_DIM
    assert a == b
    assert a != c


def test_embed_module_has_contract():
    # embed + is_available exist; we don't load the real model here.
    assert hasattr(embeddings, "embed")
    assert callable(embeddings.embed)
    assert isinstance(embeddings.is_available(), bool)


@pytest.mark.skipif(True, reason="integration: requires [embeddings] extra (torch)")
def test_real_embed_dim():
    v = embeddings.embed("hello world")
    assert len(v) == embeddings.EMBEDDING_DIM
