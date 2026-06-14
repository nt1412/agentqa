from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user import User
from app.services import auth
from app.services.errors import Unauthorized

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> User:
    try:
        if x_api_key:
            return await auth.user_from_api_key(session, x_api_key)
        if authorization and authorization.lower().startswith("bearer "):
            return await auth.user_from_token(session, authorization.split(" ", 1)[1])
    except Unauthorized as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    raise HTTPException(status_code=401, detail="missing credentials")


CurrentUser = Annotated[User, Depends(get_current_user)]
