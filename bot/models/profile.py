from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin


class Profile(Base, TimestampMixin):
    """
    Расширенный профиль участника (раздел 3 ТЗ). Связан 1-к-1 с User.
    Отдельная таблица — чтобы не раздувать users и чтобы в будущих
    этапах (achievements, quests, events, referrals) можно было
    просто добавлять связанные таблицы и джойнить счётчики,
    не трогая эту схему.
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    game_nickname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    total_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    reputation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    voice_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    activity_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<Profile user_id={self.user_id} level={self.level} xp={self.total_xp}>"
