from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin

# Редкости достижений (раздел 7 ТЗ)
RARITIES: list[str] = ["common", "rare", "epic", "legendary", "secret"]

RARITY_EMOJI: dict[str, str] = {
    "common": "⚪",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟠",
    "secret": "🔒",
}

# Метрики, по которым бот умеет проверять условие достижения автоматически.
AUTO_TRACKABLE_METRICS: set[str] = {
    "total_xp",
    "voice_seconds",
    "message_count",
    "reputation",
    "days_in_family",
}


class Achievement(Base, TimestampMixin):
    """
    Достижение (раздел 7 ТЗ). key — короткий уникальный (в рамках гильдии)
    идентификатор для ссылок/логов, отдельно от отображаемого name.
    is_secret — секретное достижение: не показывается в списке, пока не получено.
    """

    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("guild_id", "key", name="uq_achievement_guild_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    rarity: Mapped[str] = mapped_column(String(20), default="common", nullable=False)

    requirement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    requirement_amount: Mapped[int] = mapped_column(Integer, nullable=False)

    reward_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Achievement {self.key!r} rarity={self.rarity}>"


class UserAchievement(Base, TimestampMixin):
    """Разблокированное достижение конкретного участника (created_at = дата получения)."""

    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("discord_id", "achievement_id", name="uq_user_achievement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<UserAchievement discord_id={self.discord_id} achievement_id={self.achievement_id}>"
