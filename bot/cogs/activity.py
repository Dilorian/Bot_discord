from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from bot.services.db import async_session_factory
from bot.services.log_service import send_log_embed
from bot.services.profile_service import get_or_create_profile, register_activity
from bot.services.progress_service import handle_metric_event
from bot.services.settings_service import get_or_create_settings
from bot.services.user_service import get_or_create_user
from bot.services.xp_service import add_xp, get_daily_message_xp, get_level_reward_role

logger = logging.getLogger("bot.activity")


class ActivityCog(commands.Cog):
    """
    Начисление XP за сообщения и Voice (раздел 4 ТЗ) с защитой от фарма:
    cooldown между сообщениями, дневной лимит, исключение ботов,
    отключение XP в конкретных каналах.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # cooldown хранится в памяти — не нужно переживать точность
        # между рестартами, важно только не дать фармить за секунду.
        self._message_cooldowns: dict[tuple[int, int], float] = {}
        # время входа в голосовой канал: (guild_id, user_id) -> timestamp
        self._voice_joined_at: dict[tuple[int, int], float] = {}
        self.voice_xp_task.start()

    def cog_unload(self):
        self.voice_xp_task.cancel()

    async def _handle_level_up(
        self, guild: discord.Guild, member: discord.Member, new_level: int, settings
    ) -> None:
        async with async_session_factory() as session:
            reward_role_id = await get_level_reward_role(session, guild.id, new_level)

        if reward_role_id:
            role = guild.get_role(reward_role_id)
            if role:
                try:
                    await member.add_roles(role, reason=f"Достигнут {new_level} уровень")
                except discord.Forbidden:
                    logger.warning("Нет прав выдать роль %s участнику %s", role, member)

        await send_log_embed(
            self.bot,
            settings.log_channel_id,
            title="⬆️ Повышение уровня",
            description=f"{member.mention} достиг **{new_level}** уровня!",
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        key = (guild_id, message.author.id)

        async with async_session_factory() as session:
            settings = await get_or_create_settings(session, guild_id)

            if message.channel.id in (settings.xp_disabled_channels or []):
                return

            now = time.monotonic()
            last = self._message_cooldowns.get(key, 0.0)
            if now - last < settings.xp_message_cooldown_seconds:
                return
            self._message_cooldowns[key] = now

            if settings.xp_daily_cap:
                today_total = await get_daily_message_xp(session, guild_id, message.author.id)
                if today_total >= settings.xp_daily_cap:
                    return

            user = await get_or_create_user(session, message.author, guild_id)
            profile = await get_or_create_profile(session, user)

            amount = random.randint(settings.xp_message_min, settings.xp_message_max)
            profile.message_count += 1
            leveled_up, new_level = await add_xp(
                session, profile, message.author.id, amount, reason="message"
            )
            await register_activity(session, profile)

        if leveled_up:
            await self._handle_level_up(message.guild, message.author, new_level, settings)

        await handle_metric_event(
            self.bot, message.guild, message.author, {"messages": 1, "xp": amount}
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot:
            return

        key = (member.guild.id, member.id)

        # Вход в голосовой канал (и не был подключён раньше)
        if after.channel is not None and before.channel is None:
            self._voice_joined_at[key] = time.monotonic()

        # Выход из голосового канала — фиксируем длительность сессии
        elif after.channel is None and before.channel is not None:
            joined_at = self._voice_joined_at.pop(key, None)
            if joined_at is not None:
                duration = int(time.monotonic() - joined_at)
                await self._save_voice_duration(member, duration)

    async def _save_voice_duration(self, member: discord.Member, duration_seconds: int) -> None:
        if duration_seconds <= 0:
            return

        async with async_session_factory() as session:
            settings = await get_or_create_settings(session, member.guild.id)
            user = await get_or_create_user(session, member, member.guild.id)
            profile = await get_or_create_profile(session, user)

            profile.voice_seconds += duration_seconds
            xp_amount = (duration_seconds // 60) * settings.xp_voice_per_minute

            leveled_up, new_level = False, profile.level
            if xp_amount > 0:
                leveled_up, new_level = await add_xp(
                    session, profile, member.id, xp_amount, reason="voice"
                )
            await register_activity(session, profile)

        if leveled_up:
            await self._handle_level_up(member.guild, member, new_level, settings)

        await handle_metric_event(
            self.bot,
            member.guild,
            member,
            {"voice_minutes": duration_seconds // 60, "xp": xp_amount},
        )

    @tasks.loop(minutes=5.0)
    async def voice_xp_task(self):
        """
        Подстраховка: раз в 5 минут сохраняет накопленное voice-время для
        тех, кто всё ещё сидит в голосовых каналах (на случай долгих сессий
        и на случай рестарта бота — сессия не потеряется полностью).
        """
        now = time.monotonic()
        for (guild_id, user_id), joined_at in list(self._voice_joined_at.items()):
            duration = int(now - joined_at)
            if duration < 60:
                continue

            guild = self.bot.get_guild(guild_id)
            member = guild.get_member(user_id) if guild else None
            if member is None or member.voice is None or member.voice.channel is None:
                self._voice_joined_at.pop((guild_id, user_id), None)
                continue

            await self._save_voice_duration(member, duration)
            self._voice_joined_at[(guild_id, user_id)] = now  # засчитали — сдвигаем точку отсчёта

    @voice_xp_task.before_loop
    async def before_voice_xp_task(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityCog(bot))
