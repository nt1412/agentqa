from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.schemas.auth import ApiKeyResponse, LoginRequest, TokenResponse, UserOut
from app.services import auth
from app.services.errors import Unauthorized

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: SessionDep):
    try:
        user = await auth.authenticate_user(session, body.login, body.password)
    except Unauthorized as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return TokenResponse(access_token=auth.create_access_token(user.id))


@router.post("/token", response_model=ApiKeyResponse)
async def issue_api_key(session: SessionDep, user: CurrentUser):
    raw = auth.generate_api_key()
    user.api_key = auth.hash_api_key(raw)
    await session.commit()
    return ApiKeyResponse(api_key=raw)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user
