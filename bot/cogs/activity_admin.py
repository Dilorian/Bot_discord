from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.db import async_session_factory
from bot.services.log_service import log_audit_action
from bot.services.profile_service import get_or_create_profile
from bot.services.progress_service import handle_metric_event
from bot.services.reputation_service import change_reputation
from bot.services.settings_service import get_or_create_settings, update_settings
from bot.services.user_service import get_or_create_user
from bot.services.xp_service import add_xp, set_level_reward_role
from bot.utils.embeds import error_embed, info_embed, success_embed
from bot.utils.permissions import require_permission


class ActivityAdminCog(commands.Cog):
    """⚙️ Настройка XP + ручная выдача XP/репутации + награды за уровень (Этап 2)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------- /xp
    xp_group = app_commands.Group(name="xp", description="Управление системой XP")

    @xp_group.command(name="add", description="Начислить или списать XP участнику")
    @app_commands.describe(amount="Может быть отрицательным (например, штраф)")
    @require_permission("manage_xp")
    async def xp_add(
        self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str
    ):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, member, interaction.guild_id)
            profile = await get_or_create_profile(session, user)
            leveled_up, new_level = await add_xp(
                session, profile, member.id, amount, reason="manual", actor_discord_id=interaction.user.id
            )
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="xp.manual_add",
                target=str(member.id),
                details={"amount": amount, "reason": reason},
            )

        msg = f"{member.mention}: {amount:+d} XP ({reason})"
        if leveled_up:
            msg += f"\n⬆️ Новый уровень: **{new_level}**"
        await interaction.response.send_message(embed=success_embed("XP изменено", msg), ephemeral=True)

        if amount > 0:
            await handle_metric_event(self.bot, interaction.guild, member, {"xp": amount})

    @xp_group.command(name="settings_view", description="Показать текущие настройки XP")
    async def xp_settings_view(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            s = await get_or_create_settings(session, interaction.guild_id)

        channels = ", ".join(f"<#{c}>" for c in (s.xp_disabled_channels or [])) or "нет"
        embed = info_embed(
            "🎯 Настройки XP",
            f"**XP за сообщение:** {s.xp_message_min}–{s.xp_message_max}\n"
            f"**Cooldown между сообщениями:** {s.xp_message_cooldown_seconds} сек\n"
            f"**XP за минуту в Voice:** {s.xp_voice_per_minute}\n"
            f"**Дневной лимит XP за сообщения:** {s.xp_daily_cap or 'нет'}\n"
            f"**Каналы без начисления XP:** {channels}",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @xp_group.command(name="settings_set", description="Изменить настройки XP")
    @require_permission("manage_xp")
    async def xp_settings_set(
        self,
        interaction: discord.Interaction,
        message_min: int | None = None,
        message_max: int | None = None,
        cooldown_seconds: int | None = None,
        voice_per_minute: int | None = None,
        daily_cap: int | None = None,
    ):
        if message_min is not None and message_max is not None and message_min > message_max:
            await interaction.response.send_message(
                embed=error_embed("Некорректные значения", "message_min не может быть больше message_max."),
                ephemeral=True,
            )
            return

        async with async_session_factory() as session:
            await update_settings(
                session,
                interaction.guild_id,
                xp_message_min=message_min,
                xp_message_max=message_max,
                xp_message_cooldown_seconds=cooldown_seconds,
                xp_voice_per_minute=voice_per_minute,
                xp_daily_cap=daily_cap,
            )
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="xp.settings_update",
                details={
                    "message_min": message_min,
                    "message_max": message_max,
                    "cooldown_seconds": cooldown_seconds,
                    "voice_per_minute": voice_per_minute,
                    "daily_cap": daily_cap,
                },
            )

        await interaction.response.send_message(
            embed=success_embed("Настройки XP обновлены"), ephemeral=True
        )

    @xp_group.command(name="toggle_channel", description="Включить/отключить начисление XP в канале")
    @require_permission("manage_xp")
    async def xp_toggle_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        async with async_session_factory() as session:
            settings = await get_or_create_settings(session, interaction.guild_id)
            disabled = list(settings.xp_disabled_channels or [])

            if channel.id in disabled:
                disabled.remove(channel.id)
                action, state = "xp.channel_enabled", "включено"
            else:
                disabled.append(channel.id)
                action, state = "xp.channel_disabled", "отключено"

            await update_settings(session, interaction.guild_id, xp_disabled_channels=disabled)
            await log_audit_action(
                session, interaction.guild_id, interaction.user.id, action=action, target=str(channel.id)
            )

        await interaction.response.send_message(
            embed=success_embed("Готово", f"Начисление XP в {channel.mention}: {state}"),
            ephemeral=True,
        )

    # --------------------------------------------------------- /reputation
    reputation_group = app_commands.Group(name="reputation", description="Управление репутацией")

    @reputation_group.command(name="add", description="Изменить репутацию участника")
    @app_commands.describe(change="Может быть отрицательным")
    @require_permission("manage_reputation")
    async def reputation_add(
        self, interaction: discord.Interaction, member: discord.Member, change: int, reason: str
    ):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, member, interaction.guild_id)
            profile = await get_or_create_profile(session, user)
            new_reputation = await change_reputation(
                session,
                profile,
                member.id,
                interaction.guild_id,
                change,
                reason,
                actor_discord_id=interaction.user.id,
            )
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="reputation.change",
                target=str(member.id),
                details={"change": change, "reason": reason},
            )

        await interaction.response.send_message(
            embed=success_embed(
                "Репутация изменена",
                f"{member.mention}: {change:+d} ({reason}). Текущая репутация: **{new_reputation}**",
            ),
            ephemeral=True,
        )

        if change > 0:
            await handle_metric_event(
                self.bot, interaction.guild, member, {}, achievement_metrics=("reputation",)
            )

    # -------------------------------------------------------------- /level
    level_group = app_commands.Group(name="level", description="Настройка наград за уровни")

    @level_group.command(name="reward", description="Назначить роль-награду за достижение уровня")
    @require_permission("manage_xp")
    async def level_reward(
        self, interaction: discord.Interaction, level_number: int, role: discord.Role | None = None
    ):
        async with async_session_factory() as session:
            await set_level_reward_role(
                session, interaction.guild_id, level_number, role.id if role else None
            )
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="level.reward_set",
                target=str(level_number),
                details={"role_id": role.id if role else None},
            )

        desc = f"Уровень {level_number} → {role.mention}" if role else f"Награда за уровень {level_number} снята"
        await interaction.response.send_message(embed=success_embed("Готово", desc), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityAdminCog(bot))
