from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.db import async_session_factory
from bot.services.log_service import log_audit_action
from bot.services.settings_service import get_or_create_settings, update_settings
from bot.utils.embeds import info_embed, success_embed
from bot.utils.permissions import require_permission


class SettingsCog(commands.Cog):
    """Раздел ⚙️ Администрирование → Основные настройки (Этап 1)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    settings_group = app_commands.Group(
        name="settings", description="Настройки бота для этого сервера"
    )

    @settings_group.command(name="view", description="Показать текущие настройки сервера")
    async def settings_view(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            settings = await get_or_create_settings(session, interaction.guild_id)

        admin_role = (
            f"<@&{settings.admin_role_id}>" if settings.admin_role_id else "не задана"
        )
        log_channel = (
            f"<#{settings.log_channel_id}>" if settings.log_channel_id else "не задан"
        )

        embed = info_embed(
            "⚙️ Настройки сервера",
            f"**Роль администрации:** {admin_role}\n"
            f"**Канал логов:** {log_channel}\n"
            f"**Часовой пояс:** {settings.timezone}",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @settings_group.command(name="admin_role", description="Задать роль администрации")
    @require_permission("manage_settings")
    async def settings_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        async with async_session_factory() as session:
            await update_settings(session, interaction.guild_id, admin_role_id=role.id)
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="settings.admin_role",
                target=str(role.id),
            )
        await interaction.response.send_message(
            embed=success_embed("Роль администрации обновлена", role.mention), ephemeral=True
        )

    @settings_group.command(name="log_channel", description="Задать канал для логов бота")
    @require_permission("manage_settings")
    async def settings_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        async with async_session_factory() as session:
            await update_settings(session, interaction.guild_id, log_channel_id=channel.id)
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="settings.log_channel",
                target=str(channel.id),
            )
        await interaction.response.send_message(
            embed=success_embed("Канал логов обновлён", channel.mention), ephemeral=True
        )

    @settings_group.command(name="timezone", description="Задать часовой пояс (например Europe/Moscow)")
    @require_permission("manage_settings")
    async def settings_timezone(self, interaction: discord.Interaction, timezone: str):
        import pytz

        if timezone not in pytz.all_timezones:
            await interaction.response.send_message(
                embed=info_embed(
                    "Неверный часовой пояс",
                    "Пример корректного значения: `Europe/Moscow`, `Asia/Almaty`.",
                ),
                ephemeral=True,
            )
            return

        async with async_session_factory() as session:
            await update_settings(session, interaction.guild_id, timezone=timezone)
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="settings.timezone",
                target=timezone,
            )
        await interaction.response.send_message(
            embed=success_embed("Часовой пояс обновлён", timezone), ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCog(bot))
