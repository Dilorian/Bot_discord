from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.profile import Profile
from bot.models.xp import Level, XPHistory

# Формула прогрессии уровней: level = floor(sqrt(total_xp / 100)).
# Т.е. до 2 уровня нужно 100 XP, до 3 — 400 XP, до 4 — 900 XP и т.д.
XP_LEVEL_FACTOR = 100


def compute_level(total_xp: int) -> int:
    if total_xp <= 0:
        return 0
    return int(math.isqrt(total_xp // XP_LEVEL_FACTOR))


def xp_required_for_level(level: int) -> int:
    return XP_LEVEL_FACTOR * level * level


def level_progress(total_xp: int) -> tuple[int, int, int]:
    """Возвращает (xp_в_текущий_уровень, xp_нужно_до_следующего, следующий_уровень)."""
    current_level = compute_level(total_xp)
    current_floor = xp_required_for_level(current_level)
    next_level = current_level + 1
    next_floor = xp_required_for_level(next_level)
    return total_xp - current_floor, next_floor - current_floor, next_level


async def get_daily_message_xp(session: AsyncSession, guild_id: int, discord_id: int) -> int:
    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.coalesce(func.sum(XPHistory.amount), 0)).where(
            XPHistory.guild_id == guild_id,
            XPHistory.discord_id == discord_id,
            XPHistory.reason == "message",
            XPHistory.created_at >= since,
        )
    )
    return int(result.scalar_one())


async def add_xp(
    session: AsyncSession,
    profile: Profile,
    discord_id: int,
    amount: int,
    reason: str,
    actor_discord_id: Optional[int] = None,
) -> tuple[bool, int]:
    """
    Начисляет (или списывает, если amount < 0) XP и пересчитывает уровень.
    Возвращает (произошло_ли_повышение_уровня, новый_уровень).
    """
    old_level = profile.level
    profile.total_xp = max(profile.total_xp + amount, 0)
    profile.level = compute_level(profile.total_xp)

    session.add(
        XPHistory(
            guild_id=profile.guild_id,
            discord_id=discord_id,
            amount=amount,
            reason=reason,
            actor_discord_id=actor_discord_id,
        )
    )
    await session.commit()

    return profile.level > old_level, profile.level


async def get_level_reward_role(session: AsyncSession, guild_id: int, level_number: int) -> Optional[int]:
    result = await session.execute(
        select(Level).where(Level.guild_id == guild_id, Level.level_number == level_number)
    )
    level = result.scalar_one_or_none()
    return level.reward_role_id if level else None


async def set_level_reward_role(
    session: AsyncSession, guild_id: int, level_number: int, role_id: Optional[int]
) -> Level:
    result = await session.execute(
        select(Level).where(Level.guild_id == guild_id, Level.level_number == level_number)
    )
    level = result.scalar_one_or_none()
    if level is None:
        level = Level(guild_id=guild_id, level_number=level_number, reward_role_id=role_id)
        session.add(level)
    else:
        level.reward_role_id = role_id
    await session.commit()
    await session.refresh(level)
    return level
