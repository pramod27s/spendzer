import uuid

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.account import AccountIn, AccountOut, AccountUpdate
from app.services import account_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(user: CurrentUser, db: SessionDep) -> list[AccountOut]:
    return [AccountOut.model_validate(a) for a in await account_service.list_accounts(db, user)]


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(data: AccountIn, user: CurrentUser, db: SessionDep) -> AccountOut:
    return AccountOut.model_validate(await account_service.create_account(db, user, data))


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: uuid.UUID, data: AccountUpdate, user: CurrentUser, db: SessionDep
) -> AccountOut:
    account = await account_service.update_account(db, user, account_id, data)
    return AccountOut.model_validate(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> Response:
    await account_service.delete_account(db, user, account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
