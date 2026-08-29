from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin


class XPHistory(Base, TimestampMixin):
    """
    Журнал начислений/списаний XP (раздел 4 ТЗ — "Действия в журнале XP").
    Хранит источник изменения для прозрачности и будущей статистики/ТОПов.
    """

    __tablename__ = "xp_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # может быть отрицательным
    reason: Mapped[str] = mapped_column(String(100), nullable=False)  # message/voice/manual/...
    actor_discord_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # кто начислил вручную

    def __repr__(self) -> str:
        return f"<XPHistory discord_id={self.discord_id} amount={self.amount} reason={self.reason!r}>"


class Level(Base, TimestampMixin):
    """
    Настраиваемые награды за уровень (раздел 4 ТЗ — "возможность выдачи роли",
    "возможность награды"). Порог XP для перехода на уровень считается
    формулой (см. bot/services/xp_service.py), а эта таблица хранит
    только опциональные привязанные награды за конкретный уровень.
    """

    __tablename__ = "levels"
    __table_args__ = (UniqueConstraint("guild_id", "level_number", name="uq_level_guild_number"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:
        return f"<Level {self.level_number} reward_role_id={self.reward_role_id}>"
