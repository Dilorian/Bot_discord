from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin

# XP, необходимое для одного уровня Family Pass (раздел 9 ТЗ).
PASS_XP_PER_LEVEL = 500

REWARD_TYPES: list[str] = ["money", "xp", "case", "title", "role"]


class Season(Base, TimestampMixin):
    """Сезон (раздел 9 ТЗ) — собственный рейтинг, задания появятся через quest_type='seasonal'."""

    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Season {self.name!r} active={self.is_active}>"


class SeasonProgress(Base, TimestampMixin):
    """Прогресс участника в рамках сезона: сезонный XP и уровень Family Pass."""

    __tablename__ = "season_progress"
    __table_args__ = (UniqueConstraint("season_id", "discord_id", name="uq_season_progress_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    season_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pass_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<SeasonProgress season_id={self.season_id} discord_id={self.discord_id} lvl={self.pass_level}>"


class FamilyPassReward(Base, TimestampMixin):
    """Награда Family Pass за конкретный уровень конкретного сезона (раздел 9 ТЗ)."""

    __tablename__ = "family_pass_rewards"
    __table_args__ = (
        UniqueConstraint("season_id", "level_number", name="uq_family_pass_reward_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_type: Mapped[str] = mapped_column(String(30), nullable=False)  # money/xp/case/title/role
    reward_value: Mapped[str] = mapped_column(String(200), nullable=False)  # число или название

    def __repr__(self) -> str:
        return f"<FamilyPassReward season_id={self.season_id} lvl={self.level_number} {self.reward_type}={self.reward_value!r}>"


class FamilyPassClaim(Base, TimestampMixin):
    """Факт получения награды Family Pass участником (чтобы нельзя было забрать дважды)."""

    __tablename__ = "family_pass_claims"
    __table_args__ = (
        UniqueConstraint("season_id", "discord_id", "level_number", name="uq_family_pass_claim"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<FamilyPassClaim season_id={self.season_id} discord_id={self.discord_id} lvl={self.level_number}>"
