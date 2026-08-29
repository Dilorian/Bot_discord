from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """
    Таблица users — базовая учётная запись участника семьи.
    Расширенные поля профиля (XP, репутация, статистика и т.д.)
    будут добавлены на Этапе 2 в отдельной таблице profiles,
    связанной 1-к-1 с этой таблицей.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    username: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active_member: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rank_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ranks.id", ondelete="SET NULL"), nullable=True
    )

    rank: Mapped[Optional["Rank"]] = relationship("Rank", back_populates="users")

    def __repr__(self) -> str:
        return f"<User discord_id={self.discord_id} username={self.username!r}>"
