from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin


class EconomyAccount(Base, TimestampMixin):
    __tablename__ = "economy_accounts"
    __table_args__ = (UniqueConstraint("guild_id", "user_id", name="uq_economy_account"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bank_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    daily_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_daily: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    last_weekly: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    from_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    to_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ShopItem(Base, TimestampMixin):
    __tablename__ = "shop_items"
    __table_args__ = (UniqueConstraint("guild_id", "name", name="uq_shop_item_guild_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    item_type: Mapped[str] = mapped_column(String(30), default="item", nullable=False)
    item_value: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    stock: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_inventory_user_item"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CaseReward(Base, TimestampMixin):
    __tablename__ = "case_rewards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reward_value: Mapped[str] = mapped_column(String(200), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class FamilyBank(Base, TimestampMixin):
    __tablename__ = "family_bank"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
