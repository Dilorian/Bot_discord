from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin


class Achievement(Base, TimestampMixin):
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("guild_id", "name", name="uq_achievement_guild_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rarity: Mapped[str] = mapped_column(String(20), default="common", nullable=False)
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_value: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reward_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_money: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserAchievement(Base, TimestampMixin):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    achievement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class Quest(Base, TimestampMixin):
    __tablename__ = "quests"
    __table_args__ = (UniqueConstraint("guild_id", "name", name="uq_quest_guild_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quest_type: Mapped[str] = mapped_column(String(20), default="daily", nullable=False)
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reward_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_money: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_participants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class QuestProgress(Base, TimestampMixin):
    __tablename__ = "quest_progress"
    __table_args__ = (UniqueConstraint("quest_id", "user_id", name="uq_quest_progress"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    quest_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class Season(Base, TimestampMixin):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_at: Mapped[datetime] = mapped_column(nullable=False)
    end_at: Mapped[datetime] = mapped_column(nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SeasonProgress(Base, TimestampMixin):
    __tablename__ = "season_progress"
    __table_args__ = (UniqueConstraint("season_id", "user_id", name="uq_season_progress"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class FamilyPass(Base, TimestampMixin):
    __tablename__ = "family_pass"
    __table_args__ = (UniqueConstraint("season_id", "user_id", name="uq_family_pass"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_levels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class FamilyPassReward(Base, TimestampMixin):
    __tablename__ = "family_pass_rewards"
    __table_args__ = (UniqueConstraint("season_id", "level", name="uq_family_pass_reward"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reward_value: Mapped[str] = mapped_column(String(200), nullable=False)
