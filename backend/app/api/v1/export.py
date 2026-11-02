from datetime import date

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, SessionDep
from app.services import account_data_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/transactions.csv")
async def export_transactions(user: CurrentUser, db: SessionDep) -> StreamingResponse:
    """Every transaction you have, as CSV. Duplicates are included and marked."""
    rows = await account_data_service.export_rows(db, user)
    filename = f"spendzer-transactions-{date.today().isoformat()}.csv"
    return StreamingResponse(
        account_data_service.to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
