from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func, select

from bot.models.activity import Achievement, Quest, QuestProgress, Season, SeasonProgress, FamilyPass, FamilyPassReward, UserAchievement
from bot.models.profile import Profile
from bot.models.user import User
from bot.services.activity_service import active_season, unlock_achievements
from bot.services.db import async_session_factory
from bot.services.economy_service import get_account
from bot.services.log_service import log_audit_action
from bot.services.profile_service import get_or_create_profile
from bot.services.user_service import get_or_create_user
from bot.services.xp_service import add_xp
from bot.utils.embeds import error_embed, info_embed, success_embed
from bot.utils.permissions import require_permission


class ActivityPlusCog(commands.Cog):
    """Этап 3: задания, достижения, рейтинги, сезоны и Family Pass."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    quest = app_commands.Group(name="quest", description="Задания семьи")
    achievement = app_commands.Group(name="achievement", description="Достижения семьи")
    season = app_commands.Group(name="season", description="Сезоны семьи")
    family_pass = app_commands.Group(name="pass", description="Family Pass")

    @quest.command(name="list", description="Показать активные задания")
    async def quest_list(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            rows = (await session.execute(select(Quest).where(Quest.guild_id == interaction.guild_id, Quest.active.is_(True)).order_by(Quest.id.desc()).limit(15))).scalars().all()
        if not rows:
            return await interaction.response.send_message(embed=info_embed("🎯 Задания", "Активных заданий пока нет."), ephemeral=True)
        lines = [f"**#{q.id} {q.name}** — {q.description}\n`{q.condition_type}: {q.target_value}` • +{q.reward_xp} XP • ${q.reward_money:,}" for q in rows if not q.hidden]
        await interaction.response.send_message(embed=info_embed("🎯 Активные задания", "\n\n".join(lines)), ephemeral=True)

    @quest.command(name="progress", description="Показать свой прогресс заданий")
    async def quest_progress(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id)
            rows = (await session.execute(select(Quest, QuestProgress).outerjoin(QuestProgress, (QuestProgress.quest_id == Quest.id) & (QuestProgress.user_id == user.id)).where(Quest.guild_id == interaction.guild_id, Quest.active.is_(True)).order_by(Quest.id.desc()).limit(15))).all()
        lines = []
        for q, p in rows:
            value = p.progress if p else 0
            mark = "✅" if p and p.completed else "▫️"
            lines.append(f"{mark} **{q.name}** — {value}/{q.target_value}")
        await interaction.response.send_message(embed=info_embed("🎯 Мой прогресс", "\n".join(lines) or "Нет заданий."), ephemeral=True)

    @quest.command(name="create", description="Создать задание")
    @app_commands.describe(name="Название", description="Описание", quest_type="daily/weekly/seasonal/individual/group/random", condition_type="message/voice_minute", target="Цель", reward_xp="XP", reward_money="Деньги", deadline="Дедлайн ISO 8601, например 2026-09-01T20:00:00+06:00")
    @require_permission("manage_quests")
    async def quest_create(self, interaction: discord.Interaction, name: str, description: str, quest_type: str, condition_type: str, target: int, reward_xp: int = 0, reward_money: int = 0, deadline: str | None = None):
        if target <= 0 or reward_xp < 0 or reward_money < 0 or quest_type not in {"daily", "weekly", "seasonal", "individual", "group", "random"} or condition_type not in {"message", "voice_minute"}:
            return await interaction.response.send_message(embed=error_embed("Неверные параметры", "Проверьте тип задания, условие и числа."), ephemeral=True)
        parsed_deadline = None
        if deadline:
            try:
                parsed_deadline = datetime.fromisoformat(deadline)
                if parsed_deadline.tzinfo is None:
                    parsed_deadline = parsed_deadline.replace(tzinfo=timezone.utc)
            except ValueError:
                return await interaction.response.send_message(embed=error_embed("Неверный дедлайн", "Используйте ISO 8601."), ephemeral=True)
        async with async_session_factory() as session:
            q = Quest(guild_id=interaction.guild_id, name=name, description=description, quest_type=quest_type, condition_type=condition_type, target_value=target, reward_xp=reward_xp, reward_money=reward_money, deadline=parsed_deadline)
            session.add(q)
            await session.flush()
            await log_audit_action(session, interaction.guild_id, interaction.user.id, "quest.create", str(q.id), {"name": name})
            await session.commit()
        await interaction.response.send_message(embed=success_embed("Задание создано", f"#{q.id} **{name}**"), ephemeral=True)

    @quest.command(name="delete", description="Удалить задание")
    @require_permission("manage_quests")
    async def quest_delete(self, interaction: discord.Interaction, quest_id: int):
        async with async_session_factory() as session:
            q = await session.get(Quest, quest_id)
            if not q or q.guild_id != interaction.guild_id:
                return await interaction.response.send_message(embed=error_embed("Не найдено", "Задание не найдено."), ephemeral=True)
            q.active = False
            await log_audit_action(session, interaction.guild_id, interaction.user.id, "quest.delete", str(quest_id))
            await session.commit()
        await interaction.response.send_message(embed=success_embed("Задание отключено", f"#{quest_id}"), ephemeral=True)

    @achievement.command(name="list", description="Показать достижения")
    async def achievement_list(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            rows = (await session.execute(select(Achievement).where(Achievement.guild_id == interaction.guild_id, Achievement.active.is_(True)).order_by(Achievement.id))).scalars().all()
        lines = [f"**{a.name}** [{a.rarity}] — {a.description}" + (" 🔒" if a.secret else "") for a in rows]
        await interaction.response.send_message(embed=info_embed("🏆 Достижения", "\n".join(lines) or "Достижений пока нет."), ephemeral=True)

    @achievement.command(name="create", description="Создать достижение")
    @require_permission("manage_achievements")
    async def achievement_create(self, interaction: discord.Interaction, name: str, description: str, condition_type: str, condition_value: int, rarity: str = "common", reward_xp: int = 0, reward_money: int = 0, secret: bool = False):
        if condition_value <= 0 or rarity not in {"common", "rare", "epic", "legendary", "secret"}:
            return await interaction.response.send_message(embed=error_embed("Неверные параметры", "Редкость: common/rare/epic/legendary/secret."), ephemeral=True)
        async with async_session_factory() as session:
            row = Achievement(guild_id=interaction.guild_id, name=name, description=description, condition_type=condition_type, condition_value=condition_value, rarity=rarity, reward_xp=max(0, reward_xp), reward_money=max(0, reward_money), secret=secret)
            session.add(row)
            await session.flush()
            await log_audit_action(session, interaction.guild_id, interaction.user.id, "achievement.create", str(row.id), {"name": name})
            await session.commit()
        await interaction.response.send_message(embed=success_embed("Достижение создано", name), ephemeral=True)

    @achievement.command(name="me", description="Показать мои достижения")
    async def achievement_me(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id)
            rows = (await session.execute(select(Achievement).join(UserAchievement, UserAchievement.achievement_id == Achievement.id).where(UserAchievement.user_id == user.id))).scalars().all()
        await interaction.response.send_message(embed=info_embed("🏆 Мои достижения", "\n".join(f"🏅 **{a.name}** — {a.description}" for a in rows) or "Пока ничего не получено."), ephemeral=True)

    @app_commands.command(name="leaderboard", description="Рейтинг участников семьи")
    @app_commands.describe(category="xp/activity/voice/money/reputation/messages", limit="Количество участников")
    @app_commands.choices(category=[app_commands.Choice(name=x, value=x) for x in ("xp", "activity", "voice", "money", "reputation", "messages")])
    async def leaderboard(self, interaction: discord.Interaction, category: app_commands.Choice[str], limit: int = 10):
        limit = max(3, min(limit, 25))
        async with async_session_factory() as session:
            if category.value == "money":
                from bot.models.economy import EconomyAccount
                stmt = select(User, EconomyAccount.balance).join(EconomyAccount, (EconomyAccount.user_id == User.id) & (EconomyAccount.guild_id == interaction.guild_id)).where(User.guild_id == interaction.guild_id).order_by(EconomyAccount.balance.desc()).limit(limit)
                rows = (await session.execute(stmt)).all()
                lines = [f"**{i}.** <@{u.discord_id}> — ${v:,}" for i, (u, v) in enumerate(rows, 1)]
            else:
                field = {"xp": Profile.total_xp, "activity": Profile.activity_streak, "voice": Profile.voice_seconds, "reputation": Profile.reputation, "messages": Profile.message_count}[category.value]
                rows = (await session.execute(select(User, field).join(Profile, Profile.user_id == User.id).where(User.guild_id == interaction.guild_id).order_by(field.desc()).limit(limit))).all()
                lines = [f"**{i}.** <@{u.discord_id}> — {v if category.value != 'voice' else v // 3600} {'час.' if category.value == 'voice' else ''}" for i, (u, v) in enumerate(rows, 1)]
        await interaction.response.send_message(embed=info_embed(f"🏆 Топ — {category.value}", "\n".join(lines) or "Нет данных."), ephemeral=False)

    @season.command(name="create", description="Создать сезон")
    @require_permission("manage_seasons")
    async def season_create(self, interaction: discord.Interaction, name: str, start_at: str, end_at: str):
        try:
            start = datetime.fromisoformat(start_at); end = datetime.fromisoformat(end_at)
        except ValueError:
            return await interaction.response.send_message(embed=error_embed("Неверные даты", "Используйте ISO 8601."), ephemeral=True)
        if end <= start:
            return await interaction.response.send_message(embed=error_embed("Ошибка", "Дата окончания должна быть позже начала."), ephemeral=True)
        async with async_session_factory() as session:
            season = Season(guild_id=interaction.guild_id, name=name, start_at=start, end_at=end, active=False)
            session.add(season); await session.flush(); await session.commit()
        await interaction.response.send_message(embed=success_embed("Сезон создан", f"#{season.id} {name}"), ephemeral=True)

    @season.command(name="activate", description="Активировать сезон")
    @require_permission("manage_seasons")
    async def season_activate(self, interaction: discord.Interaction, season_id: int):
        async with async_session_factory() as session:
            season = await session.get(Season, season_id)
            if not season or season.guild_id != interaction.guild_id:
                return await interaction.response.send_message(embed=error_embed("Не найдено", "Сезон не найден."), ephemeral=True)
            await session.execute(__import__("sqlalchemy").update(Season).where(Season.guild_id == interaction.guild_id).values(active=False))
            season.active = True; await session.commit()
        await interaction.response.send_message(embed=success_embed("Сезон активирован", season.name), ephemeral=True)

    @season.command(name="info", description="Информация об активном сезоне")
    async def season_info(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            season = await active_season(session, interaction.guild_id)
            if not season:
                return await interaction.response.send_message(embed=info_embed("Сезон", "Активного сезона нет."), ephemeral=True)
            user = await get_or_create_user(session, interaction.user, interaction.guild_id)
            row = (await session.execute(select(SeasonProgress).where(SeasonProgress.season_id == season.id, SeasonProgress.user_id == user.id))).scalar_one_or_none()
        await interaction.response.send_message(embed=info_embed(f"🏁 {season.name}", f"Период: <t:{int(season.start_at.timestamp())}:f> — <t:{int(season.end_at.timestamp())}:f>\nОчки: **{row.points if row else 0}**\nXP сезона: **{row.xp if row else 0}**"), ephemeral=True)

    @family_pass.command(name="me", description="Мой Family Pass")
    async def pass_me(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            season = await active_season(session, interaction.guild_id)
            if not season:
                return await interaction.response.send_message(embed=info_embed("Family Pass", "Нет активного сезона."), ephemeral=True)
            user = await get_or_create_user(session, interaction.user, interaction.guild_id)
            row = (await session.execute(select(FamilyPass).where(FamilyPass.season_id == season.id, FamilyPass.user_id == user.id))).scalar_one_or_none()
            rewards = (await session.execute(select(FamilyPassReward).where(FamilyPassReward.season_id == season.id).order_by(FamilyPassReward.level))).scalars().all()
        level = row.level if row else 0; xp = row.xp if row else 0
        lines = [f"**Lv.{r.level}** — {r.reward_type}: {r.reward_value}" + (" ✅" if row and r.level in (row.claimed_levels or []) else "") for r in rewards]
        await interaction.response.send_message(embed=info_embed(f"🎫 Family Pass — {season.name}", f"Уровень: **{level}** • XP: **{xp}**\n\n" + "\n".join(lines)), ephemeral=True)

    @family_pass.command(name="reward", description="Настроить награду Family Pass")
    @require_permission("manage_pass")
    async def pass_reward(self, interaction: discord.Interaction, season_id: int, level: int, reward_type: str, reward_value: str):
        if level <= 0:
            return await interaction.response.send_message(embed=error_embed("Ошибка", "Уровень должен быть больше 0."), ephemeral=True)
        async with async_session_factory() as session:
            row = (await session.execute(select(FamilyPassReward).where(FamilyPassReward.season_id == season_id, FamilyPassReward.level == level))).scalar_one_or_none()
            if row is None:
                row = FamilyPassReward(guild_id=interaction.guild_id, season_id=season_id, level=level, reward_type=reward_type, reward_value=reward_value); session.add(row)
            else:
                row.reward_type = reward_type; row.reward_value = reward_value
            await session.commit()
        await interaction.response.send_message(embed=success_embed("Награда Family Pass сохранена", f"Lv.{level}: {reward_type} {reward_value}"), ephemeral=True)

    @family_pass.command(name="claim", description="Забрать награду уровня Family Pass")
    async def pass_claim(self, interaction: discord.Interaction, level: int):
        async with async_session_factory() as session:
            season = await active_season(session, interaction.guild_id)
            if not season:
                return await interaction.response.send_message(embed=error_embed("Family Pass", "Нет активного сезона."), ephemeral=True)
            user = await get_or_create_user(session, interaction.user, interaction.guild_id)
            progress = (await session.execute(select(FamilyPass).where(FamilyPass.season_id == season.id, FamilyPass.user_id == user.id).with_for_update())).scalar_one_or_none()
            reward = (await session.execute(select(FamilyPassReward).where(FamilyPassReward.season_id == season.id, FamilyPassReward.level == level))).scalar_one_or_none()
            if not reward:
                return await interaction.response.send_message(embed=error_embed("Награда не найдена", f"Для Lv.{level} награда не настроена."), ephemeral=True)
            if not progress or progress.level < level:
                return await interaction.response.send_message(embed=error_embed("Уровень недоступен", f"Ваш уровень Pass: {progress.level if progress else 0}."), ephemeral=True)
            claimed = list(progress.claimed_levels or [])
            if level in claimed:
                return await interaction.response.send_message(embed=error_embed("Уже получено", f"Награда Lv.{level} уже забрана."), ephemeral=True)
            if reward.reward_type == "money":
                account = await get_account(session, interaction.guild_id, user.id)
                account.balance += int(reward.reward_value)
            elif reward.reward_type == "xp":
                profile = (await session.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one()
                await add_xp(session, profile, user.id, int(reward.reward_value), "family_pass")
            claimed.append(level); progress.claimed_levels = claimed
            await session.commit()
        await interaction.response.send_message(embed=success_embed("Награда получена", f"Family Pass Lv.{level}: **{reward.reward_type} {reward.reward_value}**"), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityPlusCog(bot))
