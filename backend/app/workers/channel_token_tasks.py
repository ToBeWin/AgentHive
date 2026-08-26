"""Celery task that proactively refreshes expiring channel access tokens.

WeCom/DingTalk/Feishu access tokens expire every 2 hours. This beat task runs
every 15 minutes and refreshes any token that is within
``settings.channel_token_refresh_ahead_seconds`` (default 300s) of expiry, so
outbound pushes never block on a token fetch.

Channels without refresh credentials (``wecom_corp_id``+``wecom_secret``,
``dingtalk_app_key``+``dingtalk_app_secret``, or
``feishu_app_id``+``feishu_app_secret``) are skipped — they use static tokens
managed by the operator.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from sqlmodel import select

from app.core.database import AsyncSessionLocal
from app.models.channel import ChannelConfig
from app.schemas.channel import ChannelStatus, ChannelType
from app.services.channel_token_service import refresh_expiring_channel_tokens
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="agenthive.channel.refresh_expiring_tokens")  # type: ignore[no-untyped-call,misc]
def refresh_expiring_channel_tokens_task() -> dict[str, object]:
    """Refresh expiring channel access tokens (WeCom/DingTalk/Feishu)."""

    return asyncio.run(_refresh_expiring_channel_tokens())


async def _refresh_expiring_channel_tokens() -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ChannelConfig).where(
                ChannelConfig.status == ChannelStatus.ACTIVE.value,
                cast(Any, ChannelConfig.channel_type).in_(
                    [
                        ChannelType.WECOM.value,
                        ChannelType.DINGTALK.value,
                        ChannelType.FEISHU.value,
                    ]
                ),
            )
        )
        rows = result.scalars().all()

    channels: list[tuple[Any, ...]] = []
    for row in rows:
        config = row.config or {}
        channels.append((row.id, ChannelType(row.channel_type), config))

    diagnostics = await refresh_expiring_channel_tokens(channels)
    logger.info(
        "channel token refresh: refreshed=%d skipped=%d failed=%d",
        len(diagnostics["refreshed"]),
        len(diagnostics["skipped"]),
        len(diagnostics["failed"]),
    )
    return diagnostics
