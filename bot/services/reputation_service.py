from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.profile import Profile
from bot.models.reputation import ReputationHistory


async def change_reputation(
    session: AsyncSession,
    profile: Profile,
    discord_id: int,
    guild_id: int,
    change: int,
    reason: str,
    actor_discord_id: Optional[int] = None,
) -> int:
    """Изменяет репутацию участника и сохраняет запись в историю (раздел 5 ТЗ)."""
    profile.reputation += change
    session.add(
        ReputationHistory(
            guild_id=guild_id,
            discord_id=discord_id,
            change=change,
            reason=reason,
            actor_discord_id=actor_discord_id,
        )
    )
    await session.commit()
    return profile.reputation
