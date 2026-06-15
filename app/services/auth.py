import datetime as dt
import hashlib
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.services.errors import Unauthorized

_settings = get_settings()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    expire = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=_settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> int:
    try:
        payload = jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError) as e:
        raise Unauthorized("invalid token") from e


def generate_api_key() -> str:
    return "aqa_" + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def authenticate_user(session: AsyncSession, login: str, password: str) -> User:
    user = (await session.execute(select(User).where(User.login == login))).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise Unauthorized("bad credentials")
    if not user.active:
        raise Unauthorized("inactive user")
    return user


async def user_from_token(session: AsyncSession, token: str) -> User:
    user_id = decode_token(token)
    user = await session.get(User, user_id)
    if user is None or not user.active:
        raise Unauthorized("user not found")
    return user


async def user_from_api_key(session: AsyncSession, api_key: str) -> User:
    user = (
        await session.execute(select(User).where(User.api_key == hash_api_key(api_key)))
    ).scalar_one_or_none()
    if user is None or not user.active:
        raise Unauthorized("invalid api key")
    return user


def enrollment_allows(provided: str | None) -> bool:
    """True iff the supplied enrollment key matches the configured secret. Fails
    closed: if no AQA_MCP_ENROLL_KEY (or legacy AGENTQA_ fallback) is set, no key
    is ever accepted — so cold-start agent registration must be deliberately enabled."""
    import os

    secret = os.environ.get("AQA_MCP_ENROLL_KEY") or os.environ.get("AGENTQA_MCP_ENROLL_KEY")
    return bool(secret) and provided == secret
