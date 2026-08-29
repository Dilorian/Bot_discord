from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from bot.models.achievement import RARITY_EMOJI
from bot.models.xp import XPHistory
from bot.services import achievement_service, quest_service
from bot.services.db import async_session_factory
from bot.services.profile_service import days_in_family, get_or_create_profile
from bot.services.user_service import get_or_create_user
from bot.services.xp_service import level_progress
from bot.utils.embeds import BRAND_COLOR, info_embed

# Разделы, которые появятся на будущих этапах — сейчас только заглушка,
# чтобы кнопки из раздела 3 ТЗ уже присутствовали в интерфейсе.
_COMING_SOON = {
    "inventory": "Инвентарь появится на Этапе 4 (экономика и магазин).",
}


def _format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours:
        return f"{hours} ч {minutes} мин"
    return f"{minutes} мин"


async def _build_profile_embed(guild: discord.Guild, member: discord.Member) -> discord.Embed:
    async with async_session_factory() as session:
        user = await get_or_create_user(session, member, guild.id)
        profile = await get_or_create_profile(session, user)

    current_xp, xp_needed, next_level = level_progress(profile.total_xp)
    rank_name = None
    if user.rank_id:
        # ленивая загрузка ранга через отдельный select, чтобы не тянуть relationship вне сессии
        from bot.models.rank import Rank

        async with async_session_factory() as session:
            result = await session.execute(select(Rank).where(Rank.id == user.rank_id))
            rank = result.scalar_one_or_none()
            rank_name = rank.name if rank else None

    embed = discord.Embed(title=f"👤 Профиль — {member.display_name}", color=BRAND_COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(name="Discord ID", value=str(member.id), inline=True)
    embed.add_field(name="Discord username", value=str(member), inline=True)
    embed.add_field(name="Игровой ник", value=profile.game_nickname or "—", inline=True)

    embed.add_field(name="Ранг", value=rank_name or "не назначен", inline=True)
    embed.add_field(name="Уровень", value=str(profile.level), inline=True)
    embed.add_field(
        name="XP",
        value=f"{profile.total_xp} (до {next_level} ур.: {current_xp}/{xp_needed})",
        inline=True,
    )

    embed.add_field(name="Баланс", value="— (Этап 4)", inline=True)
    embed.add_field(name="Репутация", value=str(profile.reputation), inline=True)
    embed.add_field(name="Титул", value=profile.title or "—", inline=True)

    embed.add_field(name="Дата вступления", value=user.created_at.strftime("%d.%m.%Y"), inline=True)
    embed.add_field(name="Дней в семье", value=str(days_in_family(user)), inline=True)
    embed.add_field(name="Серия активности", value=f"{profile.activity_streak} дн.", inline=True)

    embed.add_field(name="Voice-время", value=_format_duration(profile.voice_seconds), inline=True)
    embed.add_field(name="Сообщений отправлено", value=str(profile.message_count), inline=True)

    async with async_session_factory() as session:
        user_quests = await quest_service.list_user_quests(session, guild.id, member.id)
        completed_quests = sum(1 for _, p in user_quests if p and p.is_completed)
        achievements_count = len(await achievement_service.list_unlocked(session, guild.id, member.id))

    embed.add_field(
        name="Заданий / достижений",
        value=f"{completed_quests} / {achievements_count} (мероприятия — Этап 5)",
        inline=True,
    )

    return embed


class ProfileView(discord.ui.View):
    def __init__(self, guild: discord.Guild, member: discord.Member):
        super().__init__(timeout=120)
        self.guild = guild
        self.member = member

    async def _placeholder(self, interaction: discord.Interaction, key: str):
        await interaction.response.send_message(_COMING_SOON[key], ephemeral=True)

    @discord.ui.button(label="Достижения", emoji="🏆", style=discord.ButtonStyle.secondary, row=0)
    async def achievements(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with async_session_factory() as session:
            all_achievements = await achievement_service.list_achievements(session, self.guild.id)
            unlocked = await achievement_service.list_unlocked(session, self.guild.id, self.member.id)
            unlocked_ids = {u.achievement_id for u in unlocked}

        lines = [
            f"{RARITY_EMOJI.get(a.rarity, '')} **{a.name}** — {a.description}"
            for a in all_achievements
            if a.id in unlocked_ids
        ]
        locked_count = sum(1 for a in all_achievements if a.id not in unlocked_ids and not a.is_secret)

        embed = info_embed(
            f"🏆 Достижения — {self.member.display_name}",
            "\n".join(lines) or "Пока нет полученных достижений.",
        )
        embed.set_footer(text=f"Получено {len(lines)}/{len(all_achievements)} · ещё не открыто: {locked_count}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Статистика", emoji="📊", style=discord.ButtonStyle.secondary, row=0)
    async def statistics(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, self.member, self.guild.id)
            profile = await get_or_create_profile(session, user)

        embed = info_embed(
            f"📊 Статистика — {self.member.display_name}",
            f"**Сообщений:** {profile.message_count}\n"
            f"**Voice-время:** {_format_duration(profile.voice_seconds)}\n"
            f"**Всего XP:** {profile.total_xp}\n"
            f"**Уровень:** {profile.level}\n"
            f"**Серия активности:** {profile.activity_streak} дн.\n"
            f"**Репутация:** {profile.reputation}",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Задания", emoji="🎯", style=discord.ButtonStyle.secondary, row=1)
    async def quests(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with async_session_factory() as session:
            rows = await quest_service.list_user_quests(session, self.guild.id, self.member.id)

        if not rows:
            await interaction.response.send_message("Активных заданий сейчас нет.", ephemeral=True)
            return

        lines = []
        for quest, progress in rows:
            current = progress.progress_amount if progress else 0
            if progress and progress.is_completed:
                mark = "✅" if progress.reward_claimed else "🎁 (забрать через /quests)"
            else:
                mark = f"{current}/{quest.requirement_amount}"
            lines.append(f"**{quest.title}** — {mark}")

        embed = info_embed(f"🎯 Задания — {self.member.display_name}", "\n".join(lines))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Инвентарь", emoji="💰", style=discord.ButtonStyle.secondary, row=1)
    async def inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._placeholder(interaction, "inventory")

    @discord.ui.button(label="История", emoji="📜", style=discord.ButtonStyle.secondary, row=2)
    async def history(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with async_session_factory() as session:
            result = await session.execute(
                select(XPHistory)
                .where(XPHistory.discord_id == self.member.id, XPHistory.guild_id == self.guild.id)
                .order_by(XPHistory.created_at.desc())
                .limit(10)
            )
            entries = list(result.scalars().all())

        if not entries:
            await interaction.response.send_message("История XP пока пуста.", ephemeral=True)
            return

        lines = [
            f"`{e.created_at.strftime('%d.%m %H:%M')}` {e.amount:+d} XP — {e.reason}" for e in entries
        ]
        embed = info_embed(f"📜 История XP — {self.member.display_name}", "\n".join(lines))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Назад", emoji="⬅", style=discord.ButtonStyle.primary, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await _build_profile_embed(self.guild, self.member)
        await interaction.response.edit_message(embed=embed, view=self)


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Показать профиль участника семьи")
    async def profile(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        embed = await _build_profile_embed(interaction.guild, target)
        view = ProfileView(interaction.guild, target)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
