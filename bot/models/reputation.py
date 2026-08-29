from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin


class ReputationHistory(Base, TimestampMixin):
    """
    Журнал изменений репутации (раздел 5 ТЗ — "История репутации
    должна сохраняться"). change может быть отрицательным
    (например, за нарушение).
    """

    __tablename__ = "reputation_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    change: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_discord_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:
        return f"<ReputationHistory discord_id={self.discord_id} change={self.change}>"
