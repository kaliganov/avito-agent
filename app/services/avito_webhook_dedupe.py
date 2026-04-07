"""Дедупликация входящих вебхуков Avito (повторная доставка, старые события)."""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProcessedAvitoInbound

logger = logging.getLogger(__name__)


async def try_claim_inbound(session: AsyncSession, dedupe_key: str) -> bool:
    """
    Пытаемся зарезервировать обработку события. False — такой ключ уже был (дубликат).
    """
    session.add(ProcessedAvitoInbound(dedupe_key=dedupe_key))
    try:
        await session.flush()
        return True
    except IntegrityError:
        await session.rollback()
        logger.info("webhook: пропуск — дубликат по ключу %s…", dedupe_key[:80])
        return False
