from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot.services import quest_service, economy_service
from bot.services.db import async_session_factory
from bot.services.log_service import log_audit_action
from bot.services.xp_service import add_xp
from bot.services.profile_service import get_or_create_profile
from bot.services.user_service import get_or_create_user
from bot.models.quest import QUEST_TYPES, REQUIREMENT_TYPES
from bot.utils.embeds import BRAND_COLOR, error_embed, info_embed, success_embed
from bot.utils.permissions import require_permission

_REQ_LABELS = {
    "messages": "сообщений",
    "voice_minutes": "минут в Voice",
    "xp": "XP",
    "manual": "вручную (администрацией)",
}


def _progress_bar(current: int, total: int, length: int = 10) -> str:
    total = max(total, 1)
    filled = min(int(length * current / total), length)
    return "█" * filled + "░" * (length - filled)


class QuestClaimSelect(discord.ui.Select):
    def __init__(self, guild_id: int, discord_id: int, claimable: list):
        options = [
            discord.SelectOption(
                label=f"{q.title} (+{q.reward_xp} XP)"[:100],
                value=str(q.id),
                description=(q.description or "")[:100] or None,
            )
            for q in claimable
        ]
        super().__init__(placeholder="Выберите задание, чтобы забрать награду", options=options)
        self.guild_id = guild_id
        self.discord_id = discord_id

    async def callback(self, interaction: discord.Interaction):
        quest_id = int(self.values[0])
        async with async_session_factory() as session:
            quest = await quest_service.get_quest(session, self.guild_id, quest_id)
            if quest is None:
                await interaction.response.send_message("Задание не найдено.", ephemeral=True)
                return

            progress = await quest_service.get_progress(session, quest.id, self.discord_id)
            if progress is None or not await quest_service.claim_reward(session, progress):
                await interaction.response.send_message(
                    "Награда уже забрана или задание ещё не выполнено.", ephemeral=True
                )
                return

            user = await get_or_create_user(session, interaction.user, self.guild_id)
            profile = await get_or_create_profile(session, user)
            if quest.reward_xp:
                await add_xp(
                    session, profile, self.discord_id, quest.reward_xp, reason=f"quest:{quest.id}"
                )
            if quest.reward_money:
                await economy_service.deposit(
                    session, self.guild_id, self.discord_id, quest.reward_money,
                    reason=f"Награда задания #{quest.id}",
                )
            if quest.reward_case:
                await economy_service.add_inventory(
                    session, self.guild_id, self.discord_id,
                    f"case:{quest.reward_case}", quest.reward_case, 1,
                )

        lines = [f"🎯 Награда за **{quest.title}** получена!"]
        if quest.reward_xp:
            lines.append(f"+{quest.reward_xp} XP")
        if quest.reward_money:
            lines.append(f"+{quest.reward_money}$")
        if quest.reward_case:
            lines.append(f"Кейс: {quest.reward_case}")

        await interaction.response.edit_message(
            embed=success_embed("Награда получена", "\n".join(lines)), view=None
        )


class QuestClaimView(discord.ui.View):
    def __init__(self, guild_id: int, discord_id: int, claimable: list):
        super().__init__(timeout=120)
        if claimable:
            self.add_item(QuestClaimSelect(guild_id, discord_id, claimable))


class QuestsCog(commands.Cog):
    """🎯 Система заданий (раздел 6 ТЗ): создание администрацией + прогресс/награды для участников."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    quest_group = app_commands.Group(name="quest", description="Управление заданиями (администрация)")

    @quest_group.command(name="create", description="Создать задание")
    @app_commands.choices(
        quest_type=[app_commands.Choice(name=t, value=t) for t in QUEST_TYPES],
        requirement_type=[app_commands.Choice(name=r, value=r) for r in REQUIREMENT_TYPES],
    )
    @require_permission("manage_quests")
    async def quest_create(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        quest_type: app_commands.Choice[str],
        requirement_type: app_commands.Choice[str],
        requirement_amount: int,
        reward_xp: int = 0,
        reward_money: int = 0,
        reward_case: str | None = None,
        max_participants: int | None = None,
    ):
        async with async_session_factory() as session:
            quest = await quest_service.create_quest(
                session,
                interaction.guild_id,
                title=title,
                description=description,
                quest_type=quest_type.value,
                requirement_type=requirement_type.value,
                requirement_amount=requirement_amount,
                reward_xp=reward_xp,
                reward_money=reward_money,
                reward_case=reward_case,
                max_participants=max_participants,
                created_by=interaction.user.id,
            )
            await log_audit_action(
                session, interaction.guild_id, interaction.user.id, action="quest.create", target=str(quest.id)
            )

        await interaction.response.send_message(
            embed=success_embed("Задание создано", f"**{quest.title}** (ID {quest.id})"), ephemeral=True
        )

    @quest_group.command(name="list", description="Список заданий")
    async def quest_list(self, interaction: discord.Interaction, active_only: bool = True):
        async with async_session_factory() as session:
            quests = await quest_service.list_quests(session, interaction.guild_id, active_only)

        if not quests:
            await interaction.response.send_message("Заданий пока нет.", ephemeral=True)
            return

        lines = []
        for q in quests:
            status = "🟢" if q.is_active else "⚪"
            lines.append(
                f"{status} `#{q.id}` **{q.title}** [{q.quest_type}] — "
                f"{q.requirement_amount} {_REQ_LABELS.get(q.requirement_type, q.requirement_type)} "
                f"→ +{q.reward_xp} XP"
            )
        await interaction.response.send_message(
            embed=info_embed("🎯 Задания", "\n".join(lines)), ephemeral=True
        )

    @quest_group.command(name="delete", description="Удалить задание")
    @require_permission("manage_quests")
    async def quest_delete(self, interaction: discord.Interaction, quest_id: int):
        async with async_session_factory() as session:
            quest = await quest_service.get_quest(session, interaction.guild_id, quest_id)
            if quest is None:
                await interaction.response.send_message(
                    embed=error_embed("Не найдено", f"Задание #{quest_id} не найдено."), ephemeral=True
                )
                return
            await quest_service.delete_quest(session, quest)
            await log_audit_action(
                session, interaction.guild_id, interaction.user.id, action="quest.delete", target=str(quest_id)
            )
        await interaction.response.send_message(embed=success_embed("Задание удалено"), ephemeral=True)

    @quest_group.command(name="toggle", description="Активировать/деактивировать задание")
    @require_permission("manage_quests")
    async def quest_toggle(self, interaction: discord.Interaction, quest_id: int, active: bool):
        async with async_session_factory() as session:
            quest = await quest_service.get_quest(session, interaction.guild_id, quest_id)
            if quest is None:
                await interaction.response.send_message(
                    embed=error_embed("Не найдено", f"Задание #{quest_id} не найдено."), ephemeral=True
                )
                return
            await quest_service.set_active(session, quest, active)
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="quest.toggle",
                target=str(quest_id),
                details={"active": active},
            )
        await interaction.response.send_message(
            embed=success_embed("Готово", f"Задание #{quest_id}: {'активно' if active else 'отключено'}"),
            ephemeral=True,
        )

    @quest_group.command(name="complete", description="Вручную закрыть задание участнику (requirement_type=manual)")
    @require_permission("manage_quests")
    async def quest_complete(self, interaction: discord.Interaction, quest_id: int, member: discord.Member):
        async with async_session_factory() as session:
            quest = await quest_service.get_quest(session, interaction.guild_id, quest_id)
            if quest is None:
                await interaction.response.send_message(
                    embed=error_embed("Не найдено", f"Задание #{quest_id} не найдено."), ephemeral=True
                )
                return
            await quest_service.force_complete(session, quest, member.id)
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="quest.force_complete",
                target=str(member.id),
                details={"quest_id": quest_id},
            )
        await interaction.response.send_message(
            embed=success_embed("Готово", f"{member.mention} выполнил(а) задание **{quest.title}**."),
            ephemeral=True,
        )

    @app_commands.command(name="quests", description="Мои задания и прогресс")
    async def quests(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            rows = await quest_service.list_user_quests(session, interaction.guild_id, interaction.user.id)

        if not rows:
            await interaction.response.send_message("Активных заданий сейчас нет.", ephemeral=True)
            return

        lines = []
        claimable = []
        for quest, progress in rows:
            current = progress.progress_amount if progress else 0
            if progress and progress.is_completed:
                if progress.reward_claimed:
                    mark = "✅ (награда получена)"
                else:
                    mark = "🎁 Награда доступна!"
                    claimable.append(quest)
            else:
                mark = _progress_bar(current, quest.requirement_amount)

            lines.append(
                f"**{quest.title}** [{quest.quest_type}]\n"
                f"{quest.description}\n"
                f"{current}/{quest.requirement_amount} {_REQ_LABELS.get(quest.requirement_type, quest.requirement_type)} "
                f"→ +{quest.reward_xp} XP  {mark}\n"
            )

        embed = discord.Embed(title="🎯 Мои задания", description="\n".join(lines), color=BRAND_COLOR)
        view = QuestClaimView(interaction.guild_id, interaction.user.id, claimable)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuestsCog(bot))
