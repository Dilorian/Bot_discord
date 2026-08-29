from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.rank import Rank, RankPermission
from bot.models.user import User


async def create_rank(
    session: AsyncSession,
    guild_id: int,
    name: str,
    level: int = 0,
    discord_role_id: Optional[int] = None,
) -> Rank:
    rank = Rank(guild_id=guild_id, name=name, level=level, discord_role_id=discord_role_id)
    session.add(rank)
    await session.commit()
    await session.refresh(rank)
    return rank


async def get_rank_by_name(session: AsyncSession, guild_id: int, name: str) -> Optional[Rank]:
    result = await session.execute(
        select(Rank).where(Rank.guild_id == guild_id, Rank.name == name)
    )
    return result.scalar_one_or_none()


async def list_ranks(session: AsyncSession, guild_id: int) -> list[Rank]:
    result = await session.execute(
        select(Rank).where(Rank.guild_id == guild_id).order_by(Rank.level.desc())
    )
    return list(result.scalars().all())


async def delete_rank(session: AsyncSession, rank: Rank) -> None:
    await session.delete(rank)
    await session.commit()


async def assign_rank(session: AsyncSession, user: User, rank: Rank) -> None:
    user.rank_id = rank.id
    await session.commit()


async def set_permission(
    session: AsyncSession, rank: Rank, permission_key: str, allowed: bool = True
) -> RankPermission:
    result = await session.execute(
        select(RankPermission).where(
            RankPermission.rank_id == rank.id, RankPermission.permission_key == permission_key
        )
    )
    perm = result.scalar_one_or_none()
    if perm is None:
        perm = RankPermission(rank_id=rank.id, permission_key=permission_key, allowed=allowed)
        session.add(perm)
    else:
        perm.allowed = allowed
    await session.commit()
    return perm


async def user_has_permission(session: AsyncSession, user: User, permission_key: str) -> bool:
    if user.rank_id is None:
        return False

    result = await session.execute(
        select(RankPermission).where(
            RankPermission.rank_id == user.rank_id,
            RankPermission.permission_key.in_([permission_key, "administrator"]),
            RankPermission.allowed.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None
