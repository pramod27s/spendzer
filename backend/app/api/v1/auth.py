from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.deps import SessionDep
from app.core.errors import AuthError, error_body
from app.core.rate_limit import limiter
from app.schemas.auth import AuthOut, LoginIn, RegisterIn, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()
RefreshCookie = Annotated[str | None, Cookie(alias=_settings.refresh_cookie_name)]


def _respond(response: Response, session: auth_service.Session) -> AuthOut:
    response.set_cookie(
        key=_settings.refresh_cookie_name,
        value=session.refresh.token,
        max_age=_settings.refresh_token_days * 86400,
        httponly=True,
        secure=_settings.cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
    )
    response.headers["Cache-Control"] = "no-store"
    return AuthOut(
        access_token=session.access.token,
        expires_at=session.access.expires_at,
        user=UserOut.model_validate(session.user),
    )


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, response: Response, db: SessionDep) -> AuthOut:
    return _respond(response, await auth_service.register(db, data))


@router.post("/login", response_model=AuthOut)
@limiter.limit(_settings.login_rate_limit)
async def login(request: Request, data: LoginIn, response: Response, db: SessionDep) -> AuthOut:
    return _respond(response, await auth_service.login(db, data))


@router.post("/refresh", response_model=AuthOut)
async def refresh(
    response: Response, db: SessionDep, token: RefreshCookie = None
) -> AuthOut | JSONResponse:
    try:
        session = await auth_service.refresh(db, token)
    except AuthError as exc:
        failed = JSONResponse(
            status_code=exc.status_code, content=error_body(exc.code, exc.message)
        )
        failed.delete_cookie(_settings.refresh_cookie_name, path="/api/v1/auth")
        return failed
    return _respond(response, session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(db: SessionDep, token: RefreshCookie = None) -> Response:
    await auth_service.logout(db, token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(_settings.refresh_cookie_name, path="/api/v1/auth")
    return response
