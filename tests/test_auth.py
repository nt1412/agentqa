import pytest

from app.services import auth
from app.services.errors import Unauthorized


def test_hash_and_verify_password():
    h = auth.hash_password("hunter2")
    assert h != "hunter2"
    assert auth.verify_password("hunter2", h) is True
    assert auth.verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = auth.create_access_token(user_id=42)
    assert auth.decode_token(token) == 42


def test_decode_invalid_token_raises():
    with pytest.raises(Unauthorized):
        auth.decode_token("not.a.jwt")


def test_generate_api_key_is_unique_and_prefixed():
    k1 = auth.generate_api_key()
    k2 = auth.generate_api_key()
    assert k1.startswith("aqa_")
    assert k1 != k2
