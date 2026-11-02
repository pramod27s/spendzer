from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.deps import CurrentUser, SessionDep
from app.schemas.auth import UserOut, UserUpdate
from app.services import account_data_service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("", response_model=UserOut)
async def update_me(data: UserUpdate, user: CurrentUser, db: SessionDep) -> UserOut:
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


class DeleteAccountIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(data: DeleteAccountIn, user: CurrentUser, db: SessionDep) -> Response:
    """Delete the account and every row it owns. Asks for the password again."""
    await account_data_service.delete_account(db, user, data.password)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(get_settings().refresh_cookie_name, path="/api/v1/auth")
    return response
