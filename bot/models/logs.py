from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin


class BotLog(Base, TimestampMixin):
    """
    Технические логи самого бота: запуск, перезапуск, ошибки,
    предупреждения (раздел BOT LOGS из ТЗ). Полноценное разбиение
    на все категории логов (MEMBER/MESSAGE/VOICE/... LOGS) будет
    сделано на Этапе 8 — сейчас нужен только фундамент.
    """

    __tablename__ = "bot_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)  # info/warning/error
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # startup/shutdown/error...
    message: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<BotLog {self.level} {self.event_type}>"


class AuditLog(Base, TimestampMixin):
    """
    Журнал административных действий (кто, что и когда изменил).
    Требование раздела 35 ТЗ ("логировать административные действия").
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    actor_discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # напр. "rank.create"
    target: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by={self.actor_discord_id}>"
