from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin


class Rank(Base, TimestampMixin):
    """
    Ранг семьи (иерархическая должность). Может быть привязан
    к реальной Discord-роли (discord_role_id), тогда бот будет
    синхронизировать выдачу роли при назначении ранга.
    """

    __tablename__ = "ranks"
    __table_args__ = (UniqueConstraint("guild_id", "name", name="uq_rank_guild_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    discord_role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Чем больше level — тем выше ранг в иерархии семьи.
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="rank")
    permissions: Mapped[list["RankPermission"]] = relationship(
        "RankPermission", back_populates="rank", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Rank {self.name!r} level={self.level}>"


class RankPermission(Base, TimestampMixin):
    """
    Права ранга по принципу ключ-значение, например:
    manage_ranks, manage_settings, manage_economy, view_logs, moderate.
    Новые ключи прав можно добавлять по мере роста функционала
    без изменения схемы БД.
    """

    __tablename__ = "rank_permissions"
    __table_args__ = (
        UniqueConstraint("rank_id", "permission_key", name="uq_rank_permission"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rank_id: Mapped[int] = mapped_column(
        ForeignKey("ranks.id", ondelete="CASCADE"), nullable=False
    )
    permission_key: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rank: Mapped["Rank"] = relationship("Rank", back_populates="permissions")

    def __repr__(self) -> str:
        return f"<RankPermission rank_id={self.rank_id} key={self.permission_key!r}>"


# Известные ключи прав. Список будет расти на следующих этапах
# (manage_economy, manage_events, manage_applications, moderate и т.д.)
KNOWN_PERMISSIONS: list[str] = [
    "manage_settings",
    "manage_ranks",
    "manage_permissions",
    "view_audit_logs",
    "manage_xp",  # Этап 2: ручная выдача/списание XP, настройка XP
    "manage_reputation",
    "manage_quests",
    "manage_achievements",
    "manage_seasons",
    "manage_pass",
    "manage_economy",
    "manage_cases",
    "manage_bank",
    "view_bank",
    "administrator",  # полный доступ, аналог владельца
]
