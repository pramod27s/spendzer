import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Request,
    Response,
    UploadFile,
    status,
)

from app.core.config import get_settings
from app.core.deps import CurrentUser, SessionDep
from app.core.errors import AppError
from app.core.rate_limit import limiter, user_or_ip
from app.schemas.common import Page, PageParams
from app.schemas.upload import ColumnMappingIn, SourceOut, UploadOut
from app.services import upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])
_settings = get_settings()


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(_: CurrentUser) -> list[SourceOut]:
    return upload_service.list_sources()


@router.post("", response_model=UploadOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(_settings.upload_rate_limit, key_func=user_or_ip)
async def create_upload(
    request: Request,
    background: BackgroundTasks,
    user: CurrentUser,
    db: SessionDep,
    file: Annotated[UploadFile, File()],
    account_id: Annotated[uuid.UUID, Form()],
    source_type: Annotated[str, Form(max_length=40)],
    pdf_password: Annotated[str | None, Form(max_length=128)] = None,
) -> UploadOut:
    # Read at most limit+1 bytes so an oversized file is rejected without buffering all of it.
    file_bytes = await file.read(_settings.max_upload_bytes + 1)
    if len(file_bytes) > _settings.max_upload_bytes:
        raise AppError("FILE_TOO_LARGE", "Statements must be 10 MB or smaller.", 413)
    queued = await upload_service.queue_upload(
        db,
        user,
        file_bytes=file_bytes,
        filename=file.filename or "statement",
        content_type=file.content_type,
        account_id=account_id,
        source_type=source_type,
    )
    # The PDF password goes straight to the background task: used once, never stored or logged.
    background.add_task(
        upload_service.process_upload, user.id, queued.upload.id, queued.file_bytes, pdf_password
    )
    return UploadOut.model_validate(queued.upload)


@router.get("", response_model=Page[UploadOut])
async def list_uploads(
    user: CurrentUser, db: SessionDep, params: Annotated[PageParams, Depends()]
) -> Page[UploadOut]:
    rows, total = await upload_service.list_uploads(
        db, user, offset=params.offset, limit=params.size
    )
    return Page(
        items=[UploadOut.model_validate(u) for u in rows],
        total=total,
        page=params.page,
        size=params.size,
    )


@router.get("/{upload_id}", response_model=UploadOut)
async def get_upload(upload_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> UploadOut:
    return UploadOut.model_validate(await upload_service.get_upload(db, user, upload_id))


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(upload_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> Response:
    await upload_service.delete_upload(db, user, upload_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{upload_id}/column-mapping", response_model=UploadOut, status_code=status.HTTP_202_ACCEPTED
)
async def submit_column_mapping(
    upload_id: uuid.UUID,
    data: ColumnMappingIn,
    background: BackgroundTasks,
    user: CurrentUser,
    db: SessionDep,
) -> UploadOut:
    queued = await upload_service.submit_column_mapping(db, user, upload_id, data)
    background.add_task(upload_service.process_upload, user.id, queued.upload.id, queued.file_bytes)
    return UploadOut.model_validate(queued.upload)
