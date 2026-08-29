from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot.models.season import PASS_XP_PER_LEVEL, REWARD_TYPES
from bot.services import season_service, economy_service
from bot.services.db import async_session_factory
from bot.services.log_service import log_audit_action
from bot.utils.embeds import BRAND_COLOR, error_embed, success_embed
from bot.utils.permissions import require_permission


class FamilyPassClaimSelect(discord.ui.Select):
    def __init__(self, season_id: int, claimable_levels: list[int]):
        options = [
            discord.SelectOption(label=f"Уровень {lvl}", value=str(lvl)) for lvl in claimable_levels
        ]
        super().__init__(placeholder="Выберите уровень, чтобы забрать награду", options=options)
        self.season_id = season_id

    async def callback(self, interaction: discord.Interaction):
        level = int(self.values[0])
        async with async_session_factory() as session:
            season = await season_service.get_season(session, interaction.guild_id, self.season_id)
            reward = await season_service.claim_reward(session, season, interaction.user.id, level)
            if reward is not None:
                if reward.reward_type == "money":
                    await economy_service.deposit(
                        session, interaction.guild_id, interaction.user.id, int(reward.reward_value),
                        reason=f"Family Pass Lv.{level}",
                    )
                elif reward.reward_type == "xp":
                    from bot.services.profile_service import get_or_create_profile
                    from bot.services.user_service import get_or_create_user
                    from bot.services.xp_service import add_xp
                    user = await get_or_create_user(session, interaction.user, interaction.guild_id)
                    profile = await get_or_create_profile(session, user)
                    await add_xp(
                        session, profile, interaction.user.id, max(0, int(reward.reward_value)),
                        reason=f"familypass:{level}",
                    )
                elif reward.reward_type in {"case", "title"}:
                    await economy_service.add_inventory(
                        session, interaction.guild_id, interaction.user.id,
                        f"familypass:{level}", reward.reward_value, 1,
                    )

        if reward is None:
            await interaction.response.send_message(
                "Награда уже забрана, уровень ещё не открыт, или для него не настроена награда.",
                ephemeral=True,
            )
            return

        if reward.reward_type == "role":
            try:
                role = interaction.guild.get_role(int(reward.reward_value))
                if role is not None and isinstance(interaction.user, discord.Member):
                    await interaction.user.add_roles(role, reason=f"Family Pass Lv.{level}")
            except (ValueError, discord.HTTPException, discord.Forbidden):
                pass

        await interaction.response.edit_message(
            embed=success_embed(
                "Награда Family Pass получена",
                f"Уровень {level}: **{reward.reward_type} — {reward.reward_value}**",
            ),
            view=None,
        )


class FamilyPassView(discord.ui.View):
    def __init__(self, season_id: int, claimable_levels: list[int]):
        super().__init__(timeout=120)
        if claimable_levels:
            self.add_item(FamilyPassClaimSelect(season_id, claimable_levels))


class SeasonCog(commands.Cog):
    """🗓 Сезоны и Family Pass (раздел 9 ТЗ)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    season_group = app_commands.Group(name="season", description="Управление сезонами (администрация)")

    @season_group.command(name="create", description="Создать новый сезон (закроет текущий активный)")
    @require_permission("manage_seasons")
    async def season_create(self, interaction: discord.Interaction, name: str, duration_days: int = 30):
        starts_at = datetime.now(timezone.utc)
        ends_at = starts_at + timedelta(days=duration_days)

        async with async_session_factory() as session:
            season = await season_service.create_season(session, interaction.guild_id, name, starts_at, ends_at)
            await log_audit_action(
                session, interaction.guild_id, interaction.user.id, action="season.create", target=str(season.id)
            )

        await interaction.response.send_message(
            embed=success_embed(
                "Сезон создан",
                f"**{season.name}** (ID {season.id})\nдо {ends_at.strftime('%d.%m.%Y')}",
            )
        )

    @season_group.command(name="end", description="Досрочно завершить текущий активный сезон")
    @require_permission("manage_seasons")
    async def season_end(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            season = await season_service.get_active_season(session, interaction.guild_id)
            if season is None:
                await interaction.response.send_message(
                    embed=error_embed("Нет активного сезона"), ephemeral=True
                )
                return
            await season_service.end_season(session, season)
            await log_audit_action(
                session, interaction.guild_id, interaction.user.id, action="season.end", target=str(season.id)
            )
        await interaction.response.send_message(embed=success_embed("Сезон завершён", season.name))

    @season_group.command(name="info", description="Информация об активном сезоне")
    async def season_info(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            season = await season_service.get_active_season(session, interaction.guild_id)
            if season is None:
                await interaction.response.send_message("Сейчас нет активного сезона.", ephemeral=True)
                return
            top = await season_service.top_season_xp(session, season.id, limit=5)

        lines = [f"**{season.name}**", f"Начало: {season.starts_at.strftime('%d.%m.%Y')}"]
        if season.ends_at:
            lines.append(f"Окончание: {season.ends_at.strftime('%d.%m.%Y')}")
        if top:
            lines.append("\n**ТОП сезона по XP:**")
            for i, (discord_id, xp) in enumerate(top, start=1):
                lines.append(f"`#{i}` <@{discord_id}> — {xp} XP")

        await interaction.response.send_message(
            embed=discord.Embed(title="🗓 Сезон", description="\n".join(lines), color=BRAND_COLOR)
        )

    @season_group.command(name="reward_set", description="Настроить награду Family Pass за уровень")
    @app_commands.choices(reward_type=[app_commands.Choice(name=r, value=r) for r in REWARD_TYPES])
    @require_permission("manage_seasons")
    async def season_reward_set(
        self,
        interaction: discord.Interaction,
        level_number: int,
        reward_type: app_commands.Choice[str],
        reward_value: str,
    ):
        async with async_session_factory() as session:
            season = await season_service.get_active_season(session, interaction.guild_id)
            if season is None:
                await interaction.response.send_message(
                    embed=error_embed("Нет активного сезона"), ephemeral=True
                )
                return
            await season_service.set_reward(session, season, level_number, reward_type.value, reward_value)
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="season.reward_set",
                target=str(level_number),
                details={"reward_type": reward_type.value, "reward_value": reward_value},
            )

        await interaction.response.send_message(
            embed=success_embed(
                "Награда настроена", f"Уровень {level_number}: {reward_type.value} — {reward_value}"
            ),
            ephemeral=True,
        )

    @app_commands.command(name="familypass", description="Мой прогресс Family Pass в текущем сезоне")
    async def familypass(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            season = await season_service.get_active_season(session, interaction.guild_id)
            if season is None:
                await interaction.response.send_message("Сейчас нет активного сезона.", ephemeral=True)
                return

            progress = await season_service.get_or_create_season_progress(session, season, interaction.user.id)
            rewards = await season_service.list_rewards(session, season.id)
            claimed_levels = await season_service.list_claimed_levels(session, season.id, interaction.user.id)

        into_level_xp = progress.season_xp % PASS_XP_PER_LEVEL
        lines = [
            f"Сезон: **{season.name}**",
            f"Уровень Family Pass: **{progress.pass_level}**",
            f"XP сезона: {progress.season_xp} ({into_level_xp}/{PASS_XP_PER_LEVEL} до след. уровня)",
            "",
        ]

        claimable = []
        for r in rewards:
            if r.level_number in claimed_levels:
                mark = "✅"
            elif progress.pass_level >= r.level_number:
                mark = "🎁"
                claimable.append(r.level_number)
            else:
                mark = "🔒"
            lines.append(f"{mark} Ур.{r.level_number} — {r.reward_type}: {r.reward_value}")

        if not rewards:
            lines.append("Награды для этого сезона ещё не настроены администрацией.")

        embed = discord.Embed(title="🎫 Family Pass", description="\n".join(lines), color=BRAND_COLOR)
        view = FamilyPassView(season.id, claimable)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SeasonCog(bot))
