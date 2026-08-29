"""Stage 4: economy, shop, inventory, cases and family bank.

The migration is deliberately idempotent because an earlier Stage 4 deployment
could have created some tables before failing. Existing compatible tables are
left intact; missing tables/indexes are created.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0004_stage4"
down_revision: Union[str, None] = "0003_stage3_quests_achievements_seasons"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(name)


def _column_exists(table: str, column: str) -> bool:
    """Check if a column exists in the given table."""
    bind = op.get_bind()
    return any(c["name"] == column for c in inspect(bind).get_columns(table))


def _index_exists(name: str) -> bool:
    bind = op.get_bind()
    # In case we need to check index existence, keep original logic
    if "__" in name:
        table_name = name.split("__", 1)[0]
        return any(i["name"] == name for i in inspect(bind).get_indexes(table_name))
    return False


def upgrade() -> None:
    # --- Wallets ---
    if not _table_exists("wallets"):
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
    op.execute("CREATE INDEX IF NOT EXISTS ix_wallets_guild_id ON wallets (guild_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_wallets_discord_id ON wallets (discord_id)")

    # --- Transactions ---
    if not _table_exists("transactions"):
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
    else:
        # Table already exists – add missing columns if any
        if not _column_exists("transactions", "from_discord_id"):
            op.add_column("transactions", sa.Column("from_discord_id", sa.BigInteger(), nullable=True))
        if not _column_exists("transactions", "to_discord_id"):
            op.add_column("transactions", sa.Column("to_discord_id", sa.BigInteger(), nullable=True))
        if not _column_exists("transactions", "actor_discord_id"):
            op.add_column("transactions", sa.Column("actor_discord_id", sa.BigInteger(), nullable=True))

    # Indexes – columns are guaranteed to exist now
    op.execute("CREATE INDEX IF NOT EXISTS ix_transactions_guild_id ON transactions (guild_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_transactions_from ON transactions (from_discord_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_transactions_to ON transactions (to_discord_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_transactions_created_at ON transactions (created_at)")

    # --- Shop Items ---
    if not _table_exists("shop_items"):
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
            sa.UniqueConstraint("guild_id", "item_key", name="uq_shop_item_key"),
            sa.CheckConstraint("price >= 0", name="ck_shop_price_nonnegative"),
            sa.CheckConstraint("stock IS NULL OR stock >= 0", name="ck_shop_stock_nonnegative"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_shop_items_guild_id ON shop_items (guild_id)")

    # --- Inventory Items ---
    if not _table_exists("inventory_items"):
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
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_items_guild_user ON inventory_items (guild_id, discord_id)")

    # --- Cases ---
    if not _table_exists("cases"):
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
    op.execute("CREATE INDEX IF NOT EXISTS ix_cases_guild_id ON cases (guild_id)")

    # --- Case Rewards ---
    if not _table_exists("case_rewards"):
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
    op.execute("CREATE INDEX IF NOT EXISTS ix_case_rewards_case_id ON case_rewards (case_id)")

    # --- Bank Accounts ---
    if not _table_exists("bank_accounts"):
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
    for table in ("case_rewards", "cases", "inventory_items", "shop_items", "transactions", "wallets", "bank_accounts"):
        if _table_exists(table):
            op.drop_table(table)
