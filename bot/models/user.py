from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from bot.models.economy import Wallet, InventoryItem
    from bot.models.ranks import Rank


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active_member: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rank_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ranks.id", ondelete="SET NULL"), nullable=True)

    rank: Mapped[Optional["Rank"]] = relationship("Rank", back_populates="users")

    # Экономика (Этап 4)
    wallet: Mapped[Optional["Wallet"]] = relationship(
        "Wallet",
        foreign_keys="Wallet.discord_id",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem",
        foreign_keys="InventoryItem.discord_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User discord_id={self.discord_id} username={self.username!r}>"
