from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin

# Типы заданий (раздел 6 ТЗ)
QUEST_TYPES: list[str] = ["daily", "weekly", "seasonal", "individual", "group", "random", "hidden"]

# requirement_type, которые бот умеет отслеживать автоматически (по событиям активности).
# "manual" — задание закрывается администрацией вручную (/quest complete).
AUTO_TRACKABLE_REQUIREMENT_TYPES: set[str] = {"messages", "voice_minutes", "xp"}
REQUIREMENT_TYPES: list[str] = ["messages", "voice_minutes", "xp", "manual"]


class Quest(Base, TimestampMixin):
    """
    Задание (раздел 6 ТЗ). requirement_type/requirement_amount определяют
    условие автоматического прогресса (messages/voice_minutes/xp) либо
    "manual" — администрация закрывает вручную (например, участие в
    мероприятии, которое появится на Этапе 5).
    """

    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    quest_type: Mapped[str] = mapped_column(String(20), default="individual", nullable=False)

    requirement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    requirement_amount: Mapped[int] = mapped_column(Integer, nullable=False)

    reward_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Экономика появится на Этапе 4 — сумма фиксируется уже сейчас, зачисление будет добавлено позже.
    reward_money: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_case: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    max_participants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:
        return f"<Quest {self.title!r} type={self.quest_type} req={self.requirement_type}:{self.requirement_amount}>"


class QuestProgress(Base, TimestampMixin):
    """Прогресс конкретного участника по конкретному заданию."""

    __tablename__ = "quest_progress"
    __table_args__ = (UniqueConstraint("quest_id", "discord_id", name="uq_quest_progress_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    progress_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<QuestProgress quest_id={self.quest_id} discord_id={self.discord_id} {self.progress_amount}>"
