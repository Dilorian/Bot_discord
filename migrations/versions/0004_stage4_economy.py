"""stage 4: economy, shop, inventory and cases

Revision ID: 0004_stage4
Revises: 0003_stage3
Create Date: 2026-08-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004_stage4"
down_revision: Union[str, None] = "0003_stage3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "economy_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "discord_id", name="uq_economy_account_user"),
    )
    op.create_index("ix_economy_accounts_guild_id", "economy_accounts", ["guild_id"])
    op.create_index("ix_economy_accounts_discord_id", "economy_accounts", ["discord_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("transaction_type", sa.String(40), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("target_discord_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_discord_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for col in ("guild_id", "transaction_type", "discord_id"):
        op.create_index(f"ix_transactions_{col}", "transactions", [col])

    op.create_table(
        "inventory",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("item_key", sa.String(100), nullable=False),
        sa.Column("item_name", sa.String(150), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "discord_id", "item_key", name="uq_inventory_item"),
    )
    for col in ("guild_id", "discord_id"):
        op.create_index(f"ix_inventory_{col}", "inventory", [col])

    op.create_table(
        "shop_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("item_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("item_type", sa.String(30), nullable=False),
        sa.Column("item_value", sa.String(200), nullable=False, server_default=""),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "item_key", name="uq_shop_item_key"),
    )
    op.create_index("ix_shop_items_guild_id", "shop_items", ["guild_id"])

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("case_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "case_key", name="uq_case_key"),
    )
    op.create_index("ix_cases_guild_id", "cases", ["guild_id"])

    op.create_table(
        "case_rewards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("reward_type", sa.String(30), nullable=False),
        sa.Column("reward_value", sa.String(200), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rarity", sa.String(20), nullable=False, server_default="common"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_rewards_case_id", "case_rewards", ["case_id"])
    op.create_index("ix_case_rewards_guild_id", "case_rewards", ["guild_id"])

    op.create_table(
        "family_bank",
        sa.Column("guild_id", sa.BigInteger(), primary_key=True),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("family_bank")
    op.drop_table("case_rewards")
    op.drop_table("cases")
    op.drop_table("shop_items")
    op.drop_table("inventory")
    op.drop_table("transactions")
    op.drop_table("economy_accounts")
