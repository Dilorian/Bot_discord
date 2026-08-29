from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.season import (
    PASS_XP_PER_LEVEL,
    FamilyPassClaim,
    FamilyPassReward,
    Season,
    SeasonProgress,
)


async def get_active_season(session: AsyncSession, guild_id: int) -> Optional[Season]:
    result = await session.execute(
        select(Season).where(Season.guild_id == guild_id, Season.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def create_season(
    session: AsyncSession,
    guild_id: int,
    name: str,
    starts_at: datetime,
    ends_at: Optional[datetime] = None,
) -> Season:
    """Создаёт новый сезон и деактивирует предыдущий активный (единовременно активен один сезон)."""
    current = await get_active_season(session, guild_id)
    if current is not None:
        current.is_active = False

    season = Season(guild_id=guild_id, name=name, starts_at=starts_at, ends_at=ends_at, is_active=True)
    session.add(season)
    await session.commit()
    await session.refresh(season)
    return season


async def end_season(session: AsyncSession, season: Season) -> None:
    season.is_active = False
    if season.ends_at is None:
        season.ends_at = datetime.now(timezone.utc)
    await session.commit()


async def get_season(session: AsyncSession, guild_id: int, season_id: int) -> Optional[Season]:
    result = await session.execute(
        select(Season).where(Season.guild_id == guild_id, Season.id == season_id)
    )
    return result.scalar_one_or_none()


async def list_seasons(session: AsyncSession, guild_id: int) -> list[Season]:
    result = await session.execute(
        select(Season).where(Season.guild_id == guild_id).order_by(Season.starts_at.desc())
    )
    return list(result.scalars().all())


async def get_or_create_season_progress(
    session: AsyncSession, season: Season, discord_id: int
) -> SeasonProgress:
    result = await session.execute(
        select(SeasonProgress).where(
            SeasonProgress.season_id == season.id, SeasonProgress.discord_id == discord_id
        )
    )
    progress = result.scalar_one_or_none()
    if progress is None:
        progress = SeasonProgress(season_id=season.id, guild_id=season.guild_id, discord_id=discord_id)
        session.add(progress)
        await session.flush()
    return progress


async def add_season_xp(session: AsyncSession, guild_id: int, discord_id: int, amount: int) -> None:
    if amount <= 0:
        return
    season = await get_active_season(session, guild_id)
    if season is None:
        return

    progress = await get_or_create_season_progress(session, season, discord_id)
    progress.season_xp += amount
    progress.pass_level = progress.season_xp // PASS_XP_PER_LEVEL
    await session.commit()


async def list_rewards(session: AsyncSession, season_id: int) -> list[FamilyPassReward]:
    result = await session.execute(
        select(FamilyPassReward)
        .where(FamilyPassReward.season_id == season_id)
        .order_by(FamilyPassReward.level_number)
    )
    return list(result.scalars().all())


async def set_reward(
    session: AsyncSession,
    season: Season,
    level_number: int,
    reward_type: str,
    reward_value: str,
) -> FamilyPassReward:
    result = await session.execute(
        select(FamilyPassReward).where(
            FamilyPassReward.season_id == season.id, FamilyPassReward.level_number == level_number
        )
    )
    reward = result.scalar_one_or_none()
    if reward is None:
        reward = FamilyPassReward(
            season_id=season.id,
            guild_id=season.guild_id,
            level_number=level_number,
            reward_type=reward_type,
            reward_value=reward_value,
        )
        session.add(reward)
    else:
        reward.reward_type = reward_type
        reward.reward_value = reward_value
    await session.commit()
    await session.refresh(reward)
    return reward


async def list_claimed_levels(session: AsyncSession, season_id: int, discord_id: int) -> set[int]:
    result = await session.execute(
        select(FamilyPassClaim.level_number).where(
            FamilyPassClaim.season_id == season_id, FamilyPassClaim.discord_id == discord_id
        )
    )
    return set(result.scalars().all())


async def claim_reward(
    session: AsyncSession, season: Season, discord_id: int, level_number: int
) -> Optional[FamilyPassReward]:
    """Возвращает награду при успешном получении, иначе None (не открыт уровень / уже забрано / награды нет)."""
    progress = await get_or_create_season_progress(session, season, discord_id)
    if progress.pass_level < level_number:
        return None

    already = await session.execute(
        select(FamilyPassClaim).where(
            FamilyPassClaim.season_id == season.id,
            FamilyPassClaim.discord_id == discord_id,
            FamilyPassClaim.level_number == level_number,
        )
    )
    if already.scalar_one_or_none() is not None:
        return None

    result = await session.execute(
        select(FamilyPassReward).where(
            FamilyPassReward.season_id == season.id, FamilyPassReward.level_number == level_number
        )
    )
    reward = result.scalar_one_or_none()
    if reward is None:
        return None

    session.add(
        FamilyPassClaim(
            season_id=season.id, guild_id=season.guild_id, discord_id=discord_id, level_number=level_number
        )
    )
    await session.commit()
    return reward


async def top_season_xp(session: AsyncSession, season_id: int, limit: int = 10) -> list[tuple[int, int]]:
    result = await session.execute(
        select(SeasonProgress.discord_id, SeasonProgress.season_xp)
        .where(SeasonProgress.season_id == season_id)
        .order_by(SeasonProgress.season_xp.desc())
        .limit(limit)
    )
    return [(row.discord_id, row.season_xp) for row in result.all()]
