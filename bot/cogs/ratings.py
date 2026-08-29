from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.services import rating_service
from bot.services.db import async_session_factory
from bot.utils.embeds import BRAND_COLOR, error_embed

_METRIC_CHOICES = [
    app_commands.Choice(name="XP", value="xp"),
    app_commands.Choice(name="Репутация", value="reputation"),
    app_commands.Choice(name="Voice", value="voice"),
    app_commands.Choice(name="Сообщения", value="messages"),
]

_PERIOD_CHOICES = [
    app_commands.Choice(name="день", value="day"),
    app_commands.Choice(name="неделя", value="week"),
    app_commands.Choice(name="месяц", value="month"),
    app_commands.Choice(name="сезон", value="season"),
    app_commands.Choice(name="всё время", value="all"),
]

_MEDALS = ["🥇", "🥈", "🥉"]


def _format_value(metric: str, value: int) -> str:
    if metric == "voice":
        hours, remainder = divmod(value, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours} ч {minutes} мин"
    if metric == "xp":
        return f"{value} XP"
    return str(value)


class RatingsCog(commands.Cog):
    """📊 Рейтинги участников семьи (раздел 8 ТЗ)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="top", description="Рейтинг участников семьи")
    @app_commands.choices(metric=_METRIC_CHOICES, period=_PERIOD_CHOICES)
    async def top(
        self,
        interaction: discord.Interaction,
        metric: app_commands.Choice[str],
        period: app_commands.Choice[str] = None,
    ):
        period_value = period.value if period else "all"

        if metric.value in rating_service.PERIOD_LIMITED_METRICS and period_value != "all":
            await interaction.response.send_message(
                embed=error_embed(
                    "Недоступно",
                    f"Рейтинг «{metric.name}» пока доступен только за всё время "
                    "(история по периодам появится с расширенными логами на Этапе 8).",
                ),
                ephemeral=True,
            )
            return

        async with async_session_factory() as session:
            if metric.value == "xp":
                rows = await rating_service.top_xp(session, interaction.guild_id, period_value)
            elif metric.value == "reputation":
                rows = await rating_service.top_reputation(session, interaction.guild_id, period_value)
            elif metric.value == "voice":
                rows = await rating_service.top_voice(session, interaction.guild_id)
            else:
                rows = await rating_service.top_messages(session, interaction.guild_id)

        if not rows:
            await interaction.response.send_message("Пока недостаточно данных для рейтинга.", ephemeral=True)
            return

        lines = []
        for i, (discord_id, value) in enumerate(rows, start=1):
            place = _MEDALS[i - 1] if i <= 3 else f"`#{i}`"
            lines.append(f"{place} <@{discord_id}> — **{_format_value(metric.value, value)}**")

        embed = discord.Embed(
            title=f"📊 ТОП: {metric.name} ({period.name if period else 'всё время'})",
            description="\n".join(lines),
            color=BRAND_COLOR,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RatingsCog(bot))
