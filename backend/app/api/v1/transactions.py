import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.common import Page, PageParams
from app.schemas.transaction import (
    BulkCategorizeIn,
    BulkCategorizeOut,
    ReviewQueueOut,
    TransactionCreate,
    TransactionFilters,
    TransactionOut,
    TransactionUpdate,
    TransactionUpdateOut,
)
from app.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=Page[TransactionOut])
async def list_transactions(
    user: CurrentUser,
    db: SessionDep,
    params: Annotated[PageParams, Depends()],
    filters: Annotated[TransactionFilters, Depends()],
) -> Page[TransactionOut]:
    rows, total = await transaction_service.list_transactions(
        db, user, filters, offset=params.offset, limit=params.size
    )
    return Page(
        items=[TransactionOut.model_validate(t) for t in rows],
        total=total,
        page=params.page,
        size=params.size,
    )


@router.get("/review", response_model=ReviewQueueOut)
async def review_queue(user: CurrentUser, db: SessionDep) -> ReviewQueueOut:
    """Spends we couldn't categorize and credits we couldn't explain."""
    return await transaction_service.review_queue(db, user)


@router.post("/bulk-categorize", response_model=BulkCategorizeOut)
async def bulk_categorize(
    data: BulkCategorizeIn, user: CurrentUser, db: SessionDep
) -> BulkCategorizeOut:
    """File several transactions under one category at once (e.g. every small payment)."""
    updated = await transaction_service.bulk_categorize(
        db, user, data.transaction_ids, data.category_id
    )
    return BulkCategorizeOut(updated=updated)


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    data: TransactionCreate, user: CurrentUser, db: SessionDep
) -> TransactionOut:
    return TransactionOut.model_validate(await transaction_service.create_manual(db, user, data))


@router.patch("/{txn_id}", response_model=TransactionUpdateOut)
async def update_transaction(
    txn_id: uuid.UUID, data: TransactionUpdate, user: CurrentUser, db: SessionDep
) -> TransactionUpdateOut:
    txn, moved = await transaction_service.update_transaction(db, user, txn_id, data)
    return TransactionUpdateOut(transaction=TransactionOut.model_validate(txn), recategorized=moved)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(txn_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> Response:
    await transaction_service.delete_transaction(db, user, txn_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
