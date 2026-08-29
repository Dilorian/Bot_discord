from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.models.achievement import RARITIES, RARITY_EMOJI
from bot.services import achievement_service
from bot.services.db import async_session_factory
from bot.services.log_service import log_audit_action
from bot.utils.embeds import BRAND_COLOR, error_embed, success_embed
from bot.utils.permissions import require_permission

_REQ_LABELS = {
    "total_xp": "всего XP",
    "voice_seconds": "секунд в Voice",
    "message_count": "сообщений",
    "reputation": "репутации",
    "days_in_family": "дней в семье",
}


class AchievementsCog(commands.Cog):
    """🏆 Система достижений (раздел 7 ТЗ): обычные/редкие/эпические/легендарные/секретные."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    achievement_group = app_commands.Group(
        name="achievement", description="Управление достижениями (администрация)"
    )

    @achievement_group.command(name="create", description="Создать достижение")
    @app_commands.choices(
        rarity=[app_commands.Choice(name=r, value=r) for r in RARITIES],
        requirement_type=[
            app_commands.Choice(name=r, value=r)
            for r in ["total_xp", "voice_seconds", "message_count", "reputation", "days_in_family"]
        ],
    )
    @require_permission("manage_achievements")
    async def achievement_create(
        self,
        interaction: discord.Interaction,
        key: str,
        name: str,
        description: str,
        rarity: app_commands.Choice[str],
        requirement_type: app_commands.Choice[str],
        requirement_amount: int,
        reward_xp: int = 0,
        reward_title: str | None = None,
        is_secret: bool = False,
    ):
        async with async_session_factory() as session:
            existing = await achievement_service.get_achievement_by_key(session, interaction.guild_id, key)
            if existing is not None:
                await interaction.response.send_message(
                    embed=error_embed("Уже существует", f"Достижение с ключом `{key}` уже есть."),
                    ephemeral=True,
                )
                return

            achievement = await achievement_service.create_achievement(
                session,
                interaction.guild_id,
                key=key,
                name=name,
                description=description,
                rarity=rarity.value,
                requirement_type=requirement_type.value,
                requirement_amount=requirement_amount,
                reward_xp=reward_xp,
                reward_title=reward_title,
                is_secret=is_secret,
            )
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="achievement.create",
                target=achievement.key,
            )

        await interaction.response.send_message(
            embed=success_embed("Достижение создано", f"{RARITY_EMOJI.get(rarity.value, '')} **{name}**"),
            ephemeral=True,
        )

    @achievement_group.command(name="list", description="Список всех достижений (включая секретные)")
    @require_permission("manage_achievements")
    async def achievement_list(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            items = await achievement_service.list_achievements(session, interaction.guild_id)

        if not items:
            await interaction.response.send_message("Достижений пока нет.", ephemeral=True)
            return

        lines = [
            f"{RARITY_EMOJI.get(a.rarity, '')} `{a.key}` **{a.name}** — "
            f"{a.requirement_amount} {_REQ_LABELS.get(a.requirement_type, a.requirement_type)} → +{a.reward_xp} XP"
            + (" 🔒secret" if a.is_secret else "")
            for a in items
        ]
        embed = discord.Embed(title="🏆 Все достижения", description="\n".join(lines), color=BRAND_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @achievement_group.command(name="delete", description="Удалить достижение")
    @require_permission("manage_achievements")
    async def achievement_delete(self, interaction: discord.Interaction, key: str):
        async with async_session_factory() as session:
            achievement = await achievement_service.get_achievement_by_key(session, interaction.guild_id, key)
            if achievement is None:
                await interaction.response.send_message(
                    embed=error_embed("Не найдено", f"Достижение `{key}` не найдено."), ephemeral=True
                )
                return
            await achievement_service.delete_achievement(session, achievement)
            await log_audit_action(
                session, interaction.guild_id, interaction.user.id, action="achievement.delete", target=key
            )
        await interaction.response.send_message(embed=success_embed("Достижение удалено"), ephemeral=True)

    @app_commands.command(name="achievements", description="Достижения участника")
    async def achievements(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user

        async with async_session_factory() as session:
            all_achievements = await achievement_service.list_achievements(session, interaction.guild_id)
            unlocked = await achievement_service.list_unlocked(session, interaction.guild_id, target.id)
            unlocked_ids = {u.achievement_id for u in unlocked}

        unlocked_lines = []
        locked_count = 0
        secret_locked_count = 0
        for a in all_achievements:
            if a.id in unlocked_ids:
                unlocked_lines.append(f"{RARITY_EMOJI.get(a.rarity, '')} **{a.name}** — {a.description}")
            elif a.is_secret:
                secret_locked_count += 1
            else:
                locked_count += 1

        embed = discord.Embed(
            title=f"🏆 Достижения — {target.display_name}",
            description="\n".join(unlocked_lines) or "Пока нет полученных достижений.",
            color=BRAND_COLOR,
        )
        footer = f"Получено: {len(unlocked_lines)}/{len(all_achievements)} · Ещё не открыто: {locked_count}"
        if secret_locked_count:
            footer += f" · 🔒 секретных: {secret_locked_count}"
        embed.set_footer(text=footer)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AchievementsCog(bot))
