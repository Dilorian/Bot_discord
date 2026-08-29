from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.services.db import async_session_factory, check_db_connection
from bot.services.log_service import log_bot_event, send_log_embed
from bot.services.settings_service import get_or_create_settings
from bot.services.user_service import get_or_create_user, set_active

logger = logging.getLogger("bot.events")


class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        db_ok = await check_db_connection()

        async with async_session_factory() as session:
            await log_bot_event(
                session,
                level="info" if db_ok else "error",
                event_type="startup",
                message=f"Бот запущен как {self.bot.user} (DB: {'ok' if db_ok else 'FAIL'})",
            )

        logger.info("Бот запущен как %s (guilds: %s)", self.bot.user, len(self.bot.guilds))

        try:
            synced = await self.bot.tree.sync()
            logger.info("Синхронизировано %s slash-команд", len(synced))
        except discord.HTTPException:
            logger.exception("Не удалось синхронизировать команды")

        for guild in self.bot.guilds:
            async with async_session_factory() as session:
                settings = await get_or_create_settings(session, guild.id)
            await send_log_embed(
                self.bot,
                settings.log_channel_id,
                title="🤖 Бот запущен",
                description=f"Статус БД: {'✅ ok' if db_ok else '❌ ошибка подключения'}",
                level="info" if db_ok else "error",
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with async_session_factory() as session:
            await get_or_create_user(session, member, member.guild.id)
            settings = await get_or_create_settings(session, member.guild.id)

        await send_log_embed(
            self.bot,
            settings.log_channel_id,
            title="📥 Новый участник",
            description=f"{member.mention} ({member}) присоединился к серверу.",
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        async with async_session_factory() as session:
            await set_active(session, member.id, active=False)
            settings = await get_or_create_settings(session, member.guild.id)

        await send_log_embed(
            self.bot,
            settings.log_channel_id,
            title="📤 Участник покинул сервер",
            description=f"{member} покинул(а) сервер.",
            level="warning",
        )

    @commands.Cog.listener()
    async def on_app_command_completion(
        self, interaction: discord.Interaction, command: discord.app_commands.Command
    ):
        logger.info("Команда /%s выполнена пользователем %s", command.qualified_name, interaction.user)

    async def cog_app_command_error(self, interaction, error):
        # discord.py вызывает on_error дерева команд отдельно — см. main.py setup_hook
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
