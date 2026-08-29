from __future__ import annotations

from functools import wraps
from typing import Callable

import discord
from discord import app_commands

from bot.services.db import async_session_factory
from bot.services.rank_service import user_has_permission
from bot.services.settings_service import get_or_create_settings
from bot.services.user_service import get_or_create_user


async def _is_authorized(interaction: discord.Interaction, permission_key: str) -> bool:
    member = interaction.user
    if not isinstance(member, discord.Member):
        return False

    # Владелец сервера и пользователи с правом "Управление сервером" — всегда допущены.
    if member.guild_permissions.administrator or member == interaction.guild.owner:
        return True

    async with async_session_factory() as session:
        settings = await get_or_create_settings(session, interaction.guild_id)

        # Роль администрации, заданная в /settings, тоже даёт полный доступ.
        if settings.admin_role_id and any(
            role.id == settings.admin_role_id for role in member.roles
        ):
            return True

        user = await get_or_create_user(session, member, interaction.guild_id)
        return await user_has_permission(session, user, permission_key)


def require_permission(permission_key: str) -> Callable:
    """
    Декоратор для slash-команд: пропускает только пользователей,
    у которых есть указанное право (через ранг, роль администрации
    или Discord-право "Управление сервером").
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if not await _is_authorized(interaction, permission_key):
                await interaction.response.send_message(
                    "⛔ У вас нет прав для выполнения этой команды.", ephemeral=True
                )
                return
            return await func(self, interaction, *args, **kwargs)

        return wrapper

    return decorator
