from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin


class GuildSettings(Base, TimestampMixin):
    """
    Настройки конкретного сервера (на будущее — бот может работать
    не только с одной гильдией). Помимо базовых параметров (Этап 1)
    теперь хранит настройки XP-системы (Этап 2, раздел 4 ТЗ —
    защита от фарма: cooldown, лимиты, отключение по каналам).
    Настройки экономики/магазина и т.д. будут добавлены на следующих этапах.
    """

    __tablename__ = "settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    admin_role_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    log_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)

    # --- Настройка XP (Этап 2) ---
    xp_message_min: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    xp_message_max: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    xp_message_cooldown_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    xp_voice_per_minute: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    # 0 или NULL = лимит отключён
    xp_daily_cap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # список ID каналов, где начисление XP отключено
    xp_disabled_channels: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    def __repr__(self) -> str:
        return f"<GuildSettings guild_id={self.guild_id}>"
