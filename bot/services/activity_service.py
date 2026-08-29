from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.activity import Achievement, Quest, QuestProgress, Season, SeasonProgress, FamilyPass, FamilyPassReward, UserAchievement
from bot.models.profile import Profile
from bot.services.economy_service import get_account
from bot.services.xp_service import add_xp


async def unlock_achievements(session: AsyncSession, guild_id: int, user_id: int, profile: Profile, metrics: dict) -> list[Achievement]:
    result = await session.execute(select(Achievement).where(Achievement.guild_id == guild_id, Achievement.active.is_(True)))
    achievements = result.scalars().all()
    unlocked: list[Achievement] = []
    for achievement in achievements:
        if metrics.get(achievement.condition_type, 0) < achievement.condition_value:
            continue
        exists = await session.execute(select(UserAchievement).where(UserAchievement.user_id == user_id, UserAchievement.achievement_id == achievement.id))
        if exists.scalar_one_or_none():
            continue
        session.add(UserAchievement(guild_id=guild_id, user_id=user_id, achievement_id=achievement.id))
        if achievement.reward_xp:
            await add_xp(session, profile, user_id, achievement.reward_xp, "achievement")
        if achievement.reward_money:
            account = await get_account(session, guild_id, user_id)
            account.balance += achievement.reward_money
        unlocked.append(achievement)
    if unlocked:
        await session.commit()
    return unlocked


async def ensure_quest_progress(session: AsyncSession, quest: Quest, user_id: int) -> QuestProgress:
    result = await session.execute(select(QuestProgress).where(QuestProgress.quest_id == quest.id, QuestProgress.user_id == user_id).with_for_update())
    progress = result.scalar_one_or_none()
    if progress is None:
        progress = QuestProgress(guild_id=quest.guild_id, quest_id=quest.id, user_id=user_id)
        session.add(progress)
        await session.flush()
    return progress


async def update_quest_progress(session: AsyncSession, guild_id: int, user_id: int, condition_type: str, amount: int = 1) -> list[Quest]:
    result = await session.execute(select(Quest).where(Quest.guild_id == guild_id, Quest.active.is_(True), Quest.condition_type == condition_type))
    completed: list[Quest] = []
    for quest in result.scalars().all():
        if quest.deadline and quest.deadline < datetime.now(timezone.utc):
            continue
        progress = await ensure_quest_progress(session, quest, user_id)
        if progress.completed:
            continue
        progress.progress = min(quest.target_value, progress.progress + amount)
        if progress.progress >= quest.target_value:
            progress.completed = True
            progress.completed_at = datetime.now(timezone.utc)
            profile_result = await session.execute(select(Profile).join(Profile.user).where(Profile.user_id == user_id))
            profile = profile_result.scalar_one_or_none()
            if profile and quest.reward_xp:
                await add_xp(session, profile, user_id, quest.reward_xp, "quest")
            if quest.reward_money:
                account = await get_account(session, guild_id, user_id)
                account.balance += quest.reward_money
            completed.append(quest)
    await session.commit()
    return completed


async def active_season(session: AsyncSession, guild_id: int) -> Season | None:
    result = await session.execute(select(Season).where(Season.guild_id == guild_id, Season.active.is_(True)).order_by(Season.start_at.desc()))
    return result.scalars().first()


async def add_season_points(session: AsyncSession, guild_id: int, user_id: int, points: int, xp: int = 0) -> None:
    season = await active_season(session, guild_id)
    if not season:
        return
    result = await session.execute(select(SeasonProgress).where(SeasonProgress.season_id == season.id, SeasonProgress.user_id == user_id).with_for_update())
    row = result.scalar_one_or_none()
    if row is None:
        row = SeasonProgress(guild_id=guild_id, season_id=season.id, user_id=user_id)
        session.add(row)
    row.points += points
    row.xp += xp
    await session.commit()


async def add_family_pass_xp(session: AsyncSession, guild_id: int, user_id: int, amount: int) -> None:
    """Добавляет XP активному Family Pass. 100 XP = 1 уровень Pass."""
    if amount <= 0:
        return
    season = await active_season(session, guild_id)
    if not season:
        return
    result = await session.execute(select(FamilyPass).where(FamilyPass.season_id == season.id, FamilyPass.user_id == user_id).with_for_update())
    row = result.scalar_one_or_none()
    if row is None:
        row = FamilyPass(guild_id=guild_id, season_id=season.id, user_id=user_id)
        session.add(row)
    row.xp += amount
    row.level = row.xp // 100
    await session.commit()
