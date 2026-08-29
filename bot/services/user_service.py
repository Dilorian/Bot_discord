from __future__ import annotations

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User


async def get_or_create_user(
    session: AsyncSession, member: discord.Member | discord.User, guild_id: int
) -> User:
    """
    Возвращает запись пользователя из БД, создавая её при первом обращении.
    Вызывается при входе на сервер и при первом использовании команд —
    так гарантируно, что к моменту работы с профилем/XP/экономикой
    (следующие этапы) запись уже существует.
    """
    result = await session.execute(select(User).where(User.discord_id == member.id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            discord_id=member.id,
            guild_id=guild_id,
            username=str(member),
            display_name=getattr(member, "display_name", None),
            is_bot=member.bot,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # синхронизируем актуальное имя, если поменялось
        changed = False
        if user.username != str(member):
            user.username = str(member)
            changed = True
        if getattr(member, "display_name", None) and user.display_name != member.display_name:
            user.display_name = member.display_name
            changed = True
        if changed:
            await session.commit()

    return user


async def set_active(session: AsyncSession, discord_id: int, active: bool) -> None:
    result = await session.execute(select(User).where(User.discord_id == discord_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_active_member = active
        await session.commit()
