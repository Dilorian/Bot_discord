from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.quest import Quest, QuestProgress


async def create_quest(
    session: AsyncSession,
    guild_id: int,
    title: str,
    description: str,
    quest_type: str,
    requirement_type: str,
    requirement_amount: int,
    reward_xp: int = 0,
    reward_money: int = 0,
    reward_case: Optional[str] = None,
    max_participants: Optional[int] = None,
    starts_at: Optional[datetime] = None,
    ends_at: Optional[datetime] = None,
    created_by: Optional[int] = None,
) -> Quest:
    quest = Quest(
        guild_id=guild_id,
        title=title,
        description=description,
        quest_type=quest_type,
        requirement_type=requirement_type,
        requirement_amount=requirement_amount,
        reward_xp=reward_xp,
        reward_money=reward_money,
        reward_case=reward_case,
        max_participants=max_participants,
        starts_at=starts_at,
        ends_at=ends_at,
        created_by=created_by,
    )
    session.add(quest)
    await session.commit()
    await session.refresh(quest)
    return quest


async def get_quest(session: AsyncSession, guild_id: int, quest_id: int) -> Optional[Quest]:
    result = await session.execute(
        select(Quest).where(Quest.guild_id == guild_id, Quest.id == quest_id)
    )
    return result.scalar_one_or_none()


async def list_quests(session: AsyncSession, guild_id: int, active_only: bool = False) -> list[Quest]:
    stmt = select(Quest).where(Quest.guild_id == guild_id)
    if active_only:
        stmt = stmt.where(Quest.is_active.is_(True))
    stmt = stmt.order_by(Quest.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_quest(session: AsyncSession, quest: Quest, **fields) -> Quest:
    for key, value in fields.items():
        if value is not None and hasattr(quest, key):
            setattr(quest, key, value)
    await session.commit()
    await session.refresh(quest)
    return quest


async def set_active(session: AsyncSession, quest: Quest, active: bool) -> None:
    quest.is_active = active
    await session.commit()


async def delete_quest(session: AsyncSession, quest: Quest) -> None:
    await session.delete(quest)
    await session.commit()


async def _get_or_create_progress(session: AsyncSession, quest: Quest, discord_id: int) -> QuestProgress:
    result = await session.execute(
        select(QuestProgress).where(
            QuestProgress.quest_id == quest.id, QuestProgress.discord_id == discord_id
        )
    )
    progress = result.scalar_one_or_none()
    if progress is None:
        progress = QuestProgress(quest_id=quest.id, guild_id=quest.guild_id, discord_id=discord_id)
        session.add(progress)
        await session.flush()
    return progress


async def get_progress(session: AsyncSession, quest_id: int, discord_id: int) -> Optional[QuestProgress]:
    result = await session.execute(
        select(QuestProgress).where(
            QuestProgress.quest_id == quest_id, QuestProgress.discord_id == discord_id
        )
    )
    return result.scalar_one_or_none()


async def list_user_quests(
    session: AsyncSession, guild_id: int, discord_id: int
) -> list[tuple[Quest, Optional[QuestProgress]]]:
    """Активные задания гильдии + прогресс участника по каждому (None, если ещё не начинал)."""
    now = datetime.now(timezone.utc)
    quests = await list_quests(session, guild_id, active_only=True)
    out: list[tuple[Quest, Optional[QuestProgress]]] = []
    for quest in quests:
        if quest.starts_at and now < quest.starts_at:
            continue
        if quest.ends_at and now > quest.ends_at:
            continue
        progress = await get_progress(session, quest.id, discord_id)
        out.append((quest, progress))
    return out


async def add_progress(
    session: AsyncSession, guild_id: int, discord_id: int, requirement_type: str, amount: int
) -> list[Quest]:
    """
    Увеличивает прогресс по всем активным заданиям гильдии с данным
    requirement_type (messages/voice_minutes/xp). Возвращает список
    заданий, которые в результате были только что выполнены.
    """
    if amount <= 0:
        return []

    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Quest).where(
            Quest.guild_id == guild_id,
            Quest.requirement_type == requirement_type,
            Quest.is_active.is_(True),
        )
    )
    quests = list(result.scalars().all())
    completed: list[Quest] = []

    for quest in quests:
        if quest.starts_at and now < quest.starts_at:
            continue
        if quest.ends_at and now > quest.ends_at:
            continue

        progress = await _get_or_create_progress(session, quest, discord_id)
        if progress.is_completed:
            continue

        progress.progress_amount += amount
        if progress.progress_amount >= quest.requirement_amount:
            progress.is_completed = True
            progress.completed_at = now
            completed.append(quest)

    if quests:
        await session.commit()

    return completed


async def force_complete(session: AsyncSession, quest: Quest, discord_id: int) -> QuestProgress:
    """Ручное закрытие задания администрацией (requirement_type='manual')."""
    progress = await _get_or_create_progress(session, quest, discord_id)
    progress.progress_amount = quest.requirement_amount
    progress.is_completed = True
    progress.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(progress)
    return progress


async def claim_reward(session: AsyncSession, progress: QuestProgress) -> bool:
    """Помечает награду забранной. Возвращает False, если уже забрана или задание не выполнено."""
    if not progress.is_completed or progress.reward_claimed:
        return False
    progress.reward_claimed = True
    await session.commit()
    return True
