"""Deterministic fake embedding for tests — identical text -> identical vector,
so similarity ordering is predictable without loading a real model."""

import hashlib
import math

DIM = 384


def fake_embed(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode()).digest()
    vals = [((digest[i % len(digest)] + i * 7) % 256) / 255.0 for i in range(DIM)]
    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]
