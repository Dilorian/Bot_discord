from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.achievement import Achievement, UserAchievement


async def create_achievement(
    session: AsyncSession,
    guild_id: int,
    key: str,
    name: str,
    description: str,
    rarity: str,
    requirement_type: str,
    requirement_amount: int,
    reward_xp: int = 0,
    reward_title: Optional[str] = None,
    is_secret: bool = False,
) -> Achievement:
    achievement = Achievement(
        guild_id=guild_id,
        key=key,
        name=name,
        description=description,
        rarity=rarity,
        requirement_type=requirement_type,
        requirement_amount=requirement_amount,
        reward_xp=reward_xp,
        reward_title=reward_title,
        is_secret=is_secret,
    )
    session.add(achievement)
    await session.commit()
    await session.refresh(achievement)
    return achievement


async def get_achievement_by_key(session: AsyncSession, guild_id: int, key: str) -> Optional[Achievement]:
    result = await session.execute(
        select(Achievement).where(Achievement.guild_id == guild_id, Achievement.key == key)
    )
    return result.scalar_one_or_none()


async def list_achievements(session: AsyncSession, guild_id: int) -> list[Achievement]:
    result = await session.execute(
        select(Achievement).where(Achievement.guild_id == guild_id).order_by(Achievement.requirement_amount)
    )
    return list(result.scalars().all())


async def delete_achievement(session: AsyncSession, achievement: Achievement) -> None:
    await session.delete(achievement)
    await session.commit()


async def list_unlocked(session: AsyncSession, guild_id: int, discord_id: int) -> list[UserAchievement]:
    result = await session.execute(
        select(UserAchievement).where(
            UserAchievement.guild_id == guild_id, UserAchievement.discord_id == discord_id
        )
    )
    return list(result.scalars().all())


async def is_unlocked(session: AsyncSession, discord_id: int, achievement_id: int) -> bool:
    result = await session.execute(
        select(UserAchievement).where(
            UserAchievement.discord_id == discord_id, UserAchievement.achievement_id == achievement_id
        )
    )
    return result.scalar_one_or_none() is not None


async def check_and_unlock(
    session: AsyncSession, guild_id: int, discord_id: int, metric: str, value: int
) -> list[Achievement]:
    """
    Проверяет все достижения гильдии с данным requirement_type (metric),
    порог которых уже достигнут, и разблокирует ещё не полученные.
    Возвращает список только что разблокированных достижений.
    """
    result = await session.execute(
        select(Achievement).where(
            Achievement.guild_id == guild_id,
            Achievement.requirement_type == metric,
            Achievement.requirement_amount <= value,
        )
    )
    candidates = list(result.scalars().all())
    if not candidates:
        return []

    newly_unlocked: list[Achievement] = []
    for achievement in candidates:
        if await is_unlocked(session, discord_id, achievement.id):
            continue
        session.add(
            UserAchievement(guild_id=guild_id, discord_id=discord_id, achievement_id=achievement.id)
        )
        newly_unlocked.append(achievement)

    if newly_unlocked:
        await session.commit()

    return newly_unlocked
