import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Upload


async def get(session: AsyncSession, user_id: uuid.UUID, upload_id: uuid.UUID) -> Upload | None:
    return await session.scalar(
        select(Upload).where(Upload.id == upload_id, Upload.user_id == user_id)
    )


async def get_by_hash(session: AsyncSession, user_id: uuid.UUID, file_hash: str) -> Upload | None:
    return await session.scalar(
        select(Upload).where(Upload.user_id == user_id, Upload.file_hash == file_hash)
    )


async def list_page(
    session: AsyncSession, user_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[Sequence[Upload], int]:
    base = select(Upload).where(Upload.user_id == user_id)
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await session.scalars(
        base.order_by(Upload.created_at.desc()).offset(offset).limit(limit)
    )
    return rows.all(), total


async def create(session: AsyncSession, user_id: uuid.UUID, **fields: object) -> Upload:
    upload = Upload(user_id=user_id, **fields)
    session.add(upload)
    await session.flush()
    return upload


async def delete(session: AsyncSession, upload: Upload) -> None:
    await session.delete(upload)


async def latest_upload_at(session: AsyncSession, user_id: uuid.UUID) -> datetime | None:
    return await session.scalar(
        select(func.max(Upload.created_at)).where(Upload.user_id == user_id)
    )
