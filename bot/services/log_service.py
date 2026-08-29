from __future__ import annotations

import logging
from typing import Optional

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.logs import AuditLog, BotLog

logger = logging.getLogger("bot.logs")

_LEVEL_COLORS = {
    "info": discord.Color.blurple(),
    "warning": discord.Color.orange(),
    "error": discord.Color.red(),
}


async def log_bot_event(
    session: AsyncSession,
    level: str,
    event_type: str,
    message: str,
    meta: Optional[dict] = None,
) -> None:
    """Сохраняет техническое событие бота в БД (раздел BOT LOGS)."""
    entry = BotLog(level=level, event_type=event_type, message=message, meta=meta)
    session.add(entry)
    await session.commit()

    log_fn = getattr(logger, level, logger.info)
    log_fn(f"[{event_type}] {message}")


async def log_audit_action(
    session: AsyncSession,
    guild_id: int,
    actor_discord_id: int,
    action: str,
    target: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """Сохраняет административное действие (раздел 35 ТЗ)."""
    entry = AuditLog(
        guild_id=guild_id,
        actor_discord_id=actor_discord_id,
        action=action,
        target=target,
        details=details,
    )
    session.add(entry)
    await session.commit()


async def send_log_embed(
    bot: discord.Client,
    log_channel_id: Optional[int],
    title: str,
    description: str,
    level: str = "info",
) -> None:
    """Отправляет embed в канал логов, если он настроен."""
    if not log_channel_id:
        return

    channel = bot.get_channel(log_channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(log_channel_id)
        except discord.HTTPException:
            logger.warning("Канал логов %s недоступен", log_channel_id)
            return

    embed = discord.Embed(
        title=title,
        description=description,
        color=_LEVEL_COLORS.get(level, discord.Color.greyple()),
    )
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        logger.warning("Не удалось отправить сообщение в канал логов %s", log_channel_id)
