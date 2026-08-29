from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base, TimestampMixin


class EconomyAccount(Base, TimestampMixin):
    """Личный кошелёк участника. Один аккаунт на пользователя и сервер."""

    __tablename__ = "economy_accounts"
    __table_args__ = (UniqueConstraint("guild_id", "discord_id", name="uq_economy_account_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class Transaction(Base, TimestampMixin):
    """Неизменяемая история денежных операций."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    target_discord_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    actor_discord_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class InventoryItem(Base, TimestampMixin):
    """Предметы, купленные/полученные участником."""

    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("guild_id", "discord_id", "item_key", name="uq_inventory_item"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    item_key: Mapped[str] = mapped_column(String(100), nullable=False)
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ShopItem(Base, TimestampMixin):
    """Настройка товара магазина."""

    __tablename__ = "shop_items"
    __table_args__ = (UniqueConstraint("guild_id", "item_key", name="uq_shop_item_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    item_key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)  # item/title/role/xp/case
    item_value: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stock: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NULL = unlimited
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Case(Base, TimestampMixin):
    """Кейс с настраиваемыми шансами выпадения."""

    __tablename__ = "cases"
    __table_args__ = (UniqueConstraint("guild_id", "case_key", name="uq_case_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    case_key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    stock: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CaseReward(Base, TimestampMixin):
    """Одна награда и её вес (шанс = weight / сумма weight)."""

    __tablename__ = "case_rewards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    reward_type: Mapped[str] = mapped_column(String(30), nullable=False)  # money/xp/item/title
    reward_value: Mapped[str] = mapped_column(String(200), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rarity: Mapped[str] = mapped_column(String(20), default="common", nullable=False)


class FamilyBank(Base, TimestampMixin):
    """Общий банк семьи."""

    __tablename__ = "family_bank"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
