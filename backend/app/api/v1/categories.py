import uuid

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.category import (
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    MerchantRuleIn,
    MerchantRuleOut,
)
from app.services import category_service

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(user: CurrentUser, db: SessionDep) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in await category_service.list_categories(db, user)]


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryIn, user: CurrentUser, db: SessionDep) -> CategoryOut:
    return CategoryOut.model_validate(await category_service.create_category(db, user, data))


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID, data: CategoryUpdate, user: CurrentUser, db: SessionDep
) -> CategoryOut:
    category = await category_service.update_category(db, user, category_id, data)
    return CategoryOut.model_validate(category)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> Response:
    await category_service.delete_category(db, user, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/merchant-rules", response_model=list[MerchantRuleOut])
async def list_rules(user: CurrentUser, db: SessionDep) -> list[MerchantRuleOut]:
    return [MerchantRuleOut.model_validate(r) for r in await category_service.list_rules(db, user)]


@router.post("/merchant-rules", response_model=MerchantRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(data: MerchantRuleIn, user: CurrentUser, db: SessionDep) -> MerchantRuleOut:
    return MerchantRuleOut.model_validate(await category_service.create_rule(db, user, data))


@router.delete("/merchant-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> Response:
    await category_service.delete_rule(db, user, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
