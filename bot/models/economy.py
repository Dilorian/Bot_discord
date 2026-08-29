from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, JSON, Boolean, ForeignKey,
    CheckConstraint, UniqueConstraint, func, and_
)
from sqlalchemy.orm import relationship
from bot.models.base import Base

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    discord_id = Column(BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), nullable=False)
    balance = Column(BigInteger, nullable=False, server_default="0")
    lifetime_earned = Column(BigInteger, nullable=False, server_default="0")
    lifetime_spent = Column(BigInteger, nullable=False, server_default="0")
    daily_claimed_at = Column(DateTime(timezone=True), nullable=True)
    weekly_claimed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("guild_id", "discord_id", name="uq_wallet_guild_user"),
        CheckConstraint("balance >= 0", name="ck_wallet_balance_nonnegative"),
    )
    user = relationship("User", foreign_keys=[discord_id], back_populates="wallet", uselist=False)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    actor_discord_id = Column(BigInteger, nullable=True)
    from_discord_id = Column(BigInteger, nullable=True)
    to_discord_id = Column(BigInteger, nullable=True)
    amount = Column(BigInteger, nullable=False)
    balance_after = Column(BigInteger, nullable=True)
    transaction_type = Column(String(40), nullable=False)
    description = Column(String(300), nullable=False, server_default="")
    reference = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Явные отношения без внешних ключей (чтобы не создавать циклических зависимостей)
    from_user = relationship(
        "User",
        foreign_keys=[from_discord_id],
        primaryjoin="User.discord_id == Transaction.from_discord_id",
        viewonly=True
    )
    to_user = relationship(
        "User",
        foreign_keys=[to_discord_id],
        primaryjoin="User.discord_id == Transaction.to_discord_id",
        viewonly=True
    )
    actor_user = relationship(
        "User",
        foreign_keys=[actor_discord_id],
        primaryjoin="User.discord_id == Transaction.actor_discord_id",
        viewonly=True
    )

class ShopItem(Base):
    __tablename__ = "shop_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=False, server_default="")
    item_type = Column(String(40), nullable=False, server_default="item")
    item_key = Column(String(120), nullable=False)
    price = Column(BigInteger, nullable=False)
    stock = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("guild_id", "item_key", name="uq_shop_item_key"),
        CheckConstraint("price >= 0", name="ck_shop_price_nonnegative"),
        CheckConstraint("stock IS NULL OR stock >= 0", name="ck_shop_stock_nonnegative"),
    )
    inventory_items = relationship(
        "InventoryItem",
        primaryjoin="and_(ShopItem.guild_id == InventoryItem.guild_id, ShopItem.item_key == InventoryItem.item_key)",
        foreign_keys="[InventoryItem.guild_id, InventoryItem.item_key]",
        back_populates="shop_item"
    )

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    discord_id = Column(BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), nullable=False)
    item_key = Column(String(120), nullable=False)
    name = Column(String(120), nullable=False)
    item_type = Column(String(40), nullable=False, server_default="item")
    quantity = Column(Integer, nullable=False, server_default="1")
    # Исправлено: поле называется extra_data, но в БД колонка metadata
    extra_data = Column(JSON, name="metadata", nullable=False, server_default=func.text("'{}'::json"))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("guild_id", "discord_id", "item_key", name="uq_inventory_item"),
        CheckConstraint("quantity > 0", name="ck_inventory_quantity_positive"),
    )
    user = relationship("User", foreign_keys=[discord_id], back_populates="inventory_items")
    shop_item = relationship(
        "ShopItem",
        primaryjoin="and_(InventoryItem.guild_id == ShopItem.guild_id, InventoryItem.item_key == ShopItem.item_key)",
        foreign_keys="[InventoryItem.guild_id, InventoryItem.item_key]",
        back_populates="inventory_items"
    )

class Case(Base):
    __tablename__ = "cases"
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    key = Column(String(100), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=False, server_default="")
    price = Column(BigInteger, nullable=False)
    stock = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("guild_id", "key", name="uq_case_guild_key"),
        CheckConstraint("price >= 0", name="ck_case_price_nonnegative"),
    )
    rewards = relationship("CaseReward", back_populates="case", cascade="all, delete-orphan")

class CaseReward(Base):
    __tablename__ = "case_rewards"
    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    reward_type = Column(String(40), nullable=False)
    reward_value = Column(String(200), nullable=False)
    amount = Column(BigInteger, nullable=False, server_default="0")
    weight = Column(Integer, nullable=False, server_default="1")
    rarity = Column(String(20), nullable=False, server_default="Common")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint("weight > 0", name="ck_case_reward_weight_positive"),
    )
    case = relationship("Case", back_populates="rewards")

class BankAccount(Base):
    __tablename__ = "bank_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, unique=True)
    balance = Column(BigInteger, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("guild_id", name="uq_bank_guild"),
        CheckConstraint("balance >= 0", name="ck_bank_balance_nonnegative"),
    )
