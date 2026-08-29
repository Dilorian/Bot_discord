from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.profile import Profile
from bot.models.reputation import ReputationHistory
from bot.models.xp import XPHistory
from bot.services import season_service

# Периоды, доступные для рейтингов по разделу 8 ТЗ.
PERIODS: list[str] = ["day", "week", "month", "season", "all"]
# Voice и сообщения считаются только нарастающим итогом (в profiles) —
# отдельной истории по времени для них пока нет (появится вместе с
# расширенными ACTIVITY LOGS на Этапе 8), поэтому для них доступен только period="all".
PERIOD_LIMITED_METRICS: set[str] = {"voice", "messages"}


def _period_start(period: str) -> Optional[datetime]:
    now = datetime.now(timezone.utc)
    if period == "day":
        return now - timedelta(days=1)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    return None


async def top_xp(session: AsyncSession, guild_id: int, period: str, limit: int = 10) -> list[tuple[int, int]]:
    if period == "season":
        season = await season_service.get_active_season(session, guild_id)
        if season is None:
            return []
        return await season_service.top_season_xp(session, season.id, limit)

    # Для "all" since=None — сумма по всей истории xp_history, что эквивалентно
    # total_xp профиля (xp_history — единственный источник изменений XP).
    since = _period_start(period)
    stmt = select(XPHistory.discord_id, func.sum(XPHistory.amount).label("total")).where(
        XPHistory.guild_id == guild_id
    )
    if since is not None:
        stmt = stmt.where(XPHistory.created_at >= since)
    stmt = stmt.group_by(XPHistory.discord_id).having(func.sum(XPHistory.amount) > 0)
    stmt = stmt.order_by(func.sum(XPHistory.amount).desc()).limit(limit)

    result = await session.execute(stmt)
    return [(row.discord_id, int(row.total)) for row in result.all()]


async def top_reputation(
    session: AsyncSession, guild_id: int, period: str, limit: int = 10
) -> list[tuple[int, int]]:
    since = _period_start(period) if period != "season" else None
    stmt = select(
        ReputationHistory.discord_id, func.sum(ReputationHistory.change).label("total")
    ).where(ReputationHistory.guild_id == guild_id)
    if since is not None:
        stmt = stmt.where(ReputationHistory.created_at >= since)
    stmt = stmt.group_by(ReputationHistory.discord_id).having(func.sum(ReputationHistory.change) > 0)
    stmt = stmt.order_by(func.sum(ReputationHistory.change).desc()).limit(limit)

    result = await session.execute(stmt)
    return [(row.discord_id, int(row.total)) for row in result.all()]


async def top_voice(session: AsyncSession, guild_id: int, limit: int = 10) -> list[tuple[int, int]]:
    """Только all-time (см. PERIOD_LIMITED_METRICS)."""
    from bot.models.user import User

    result = await session.execute(
        select(User.discord_id, Profile.voice_seconds)
        .join(User, User.id == Profile.user_id)
        .where(Profile.guild_id == guild_id, Profile.voice_seconds > 0)
        .order_by(Profile.voice_seconds.desc())
        .limit(limit)
    )
    return [(row.discord_id, int(row.voice_seconds)) for row in result.all()]


async def top_messages(session: AsyncSession, guild_id: int, limit: int = 10) -> list[tuple[int, int]]:
    """Только all-time (см. PERIOD_LIMITED_METRICS)."""
    from bot.models.user import User

    result = await session.execute(
        select(User.discord_id, Profile.message_count)
        .join(User, User.id == Profile.user_id)
        .where(Profile.guild_id == guild_id, Profile.message_count > 0)
        .order_by(Profile.message_count.desc())
        .limit(limit)
    )
    return [(row.discord_id, int(row.message_count)) for row in result.all()]
