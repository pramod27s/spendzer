from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AuthError
from app.core.security import decode_token
from app.models import User
from app.repositories import user_repo

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise AuthError()
    claims = decode_token(credentials.credentials, "access")
    if claims is None:
        raise AuthError("TOKEN_INVALID", "Session expired. Please sign in again.")
    user = await user_repo.get(session, claims.user_id)
    if user is None:
        raise AuthError("TOKEN_INVALID", "Session expired. Please sign in again.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
