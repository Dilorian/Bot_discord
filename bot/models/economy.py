from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin


class Wallet(Base, TimestampMixin):
    __tablename__ = "wallets"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    lifetime_earned: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    lifetime_spent: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    daily_claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    weekly_claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    actor_discord_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    from_discord_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    to_discord_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[Optional[int]] = mapped_column(BigInteger)
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=__import__("sqlalchemy").func.now(), nullable=False)


class ShopItem(Base, TimestampMixin):
    __tablename__ = "shop_items"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    item_type: Mapped[str] = mapped_column(String(40), default="item", nullable=False)
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stock: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger)


class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    item_type: Mapped[str] = mapped_column(String(40), default="item", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Case(Base, TimestampMixin):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stock: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger)


class CaseReward(Base):
    __tablename__ = "case_rewards"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    reward_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reward_value: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rarity: Mapped[str] = mapped_column(String(20), default="Common", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=__import__("sqlalchemy").func.now(), nullable=False)


class BankAccount(Base, TimestampMixin):
    __tablename__ = "bank_accounts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
