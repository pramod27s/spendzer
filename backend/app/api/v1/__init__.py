from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    alerts,
    analytics,
    auth,
    categories,
    export,
    me,
    plans,
    recurring,
    transactions,
    uploads,
)

api_router = APIRouter(prefix="/api/v1")
for module in (
    auth,
    me,
    accounts,
    uploads,
    transactions,
    categories,
    analytics,
    recurring,
    plans,
    alerts,
    export,
):
    api_router.include_router(module.router)
