from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.settings import GuildSettings


async def get_or_create_settings(session: AsyncSession, guild_id: int) -> GuildSettings:
    result = await session.execute(
        select(GuildSettings).where(GuildSettings.guild_id == guild_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = GuildSettings(guild_id=guild_id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


async def update_settings(session: AsyncSession, guild_id: int, **fields) -> GuildSettings:
    settings = await get_or_create_settings(session, guild_id)
    for key, value in fields.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
    await session.commit()
    await session.refresh(settings)
    return settings
