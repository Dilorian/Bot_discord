"""Stage 4: economy, shop, inventory, cases and family bank.

Revision ID: 0004_stage4
Revises: 0003_stage3_quests_achievements_seasons
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0004_stage4"
down_revision: Union[str, None] = "0003_stage3_quests_achievements_seasons"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lifetime_earned", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lifetime_spent", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("daily_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("weekly_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "discord_id", name="uq_wallet_guild_user"),
        sa.CheckConstraint("balance >= 0", name="ck_wallet_balance_nonnegative"),
    )
    op.create_index("ix_wallets_guild_id", "wallets", ["guild_id"])
    op.create_index("ix_wallets_discord_id", "wallets", ["discord_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_discord_id", sa.BigInteger(), nullable=True),
        sa.Column("from_discord_id", sa.BigInteger(), nullable=True),
        sa.Column("to_discord_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=True),
        sa.Column("transaction_type", sa.String(40), nullable=False),
        sa.Column("description", sa.String(300), nullable=False, server_default=""),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transactions_guild_id", "transactions", ["guild_id"])
    op.create_index("ix_transactions_from", "transactions", ["from_discord_id"])
    op.create_index("ix_transactions_to", "transactions", ["to_discord_id"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])

    op.create_table(
        "shop_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("item_type", sa.String(40), nullable=False, server_default="item"),
        sa.Column("item_key", sa.String(120), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_shop_price_nonnegative"),
        sa.CheckConstraint("stock IS NULL OR stock >= 0", name="ck_shop_stock_nonnegative"),
    )
    op.create_index("ix_shop_items_guild_id", "shop_items", ["guild_id"])

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("item_key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("item_type", sa.String(40), nullable=False, server_default="item"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "discord_id", "item_key", name="uq_inventory_item"),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_quantity_positive"),
    )
    op.create_index("ix_inventory_items_guild_user", "inventory_items", ["guild_id", "discord_id"])

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "key", name="uq_case_guild_key"),
        sa.CheckConstraint("price >= 0", name="ck_case_price_nonnegative"),
    )
    op.create_index("ix_cases_guild_id", "cases", ["guild_id"])

    op.create_table(
        "case_rewards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reward_type", sa.String(40), nullable=False),
        sa.Column("reward_value", sa.String(200), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rarity", sa.String(20), nullable=False, server_default="Common"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("weight > 0", name="ck_case_reward_weight_positive"),
    )
    op.create_index("ix_case_rewards_case_id", "case_rewards", ["case_id"])

    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", name="uq_bank_guild"),
        sa.CheckConstraint("balance >= 0", name="ck_bank_balance_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("case_rewards")
    op.drop_table("cases")
    op.drop_table("inventory_items")
    op.drop_table("shop_items")
    op.drop_table("transactions")
    op.drop_table("wallets")
    op.drop_table("bank_accounts")
