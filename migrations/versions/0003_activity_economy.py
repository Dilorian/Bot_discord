"""stage 3-4: activity, seasons, family pass and economy

Revision ID: 0003_activity_economy
Revises: 0002_stage2
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003_activity_economy"
down_revision: Union[str, None] = "0002_stage2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rarity", sa.String(20), nullable=False, server_default="common"), sa.Column("condition_type", sa.String(50), nullable=False),
        sa.Column("condition_value", sa.Integer(), nullable=False, server_default="1"), sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_money", sa.Integer(), nullable=False, server_default="0"), sa.Column("secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "name", name="uq_achievement_guild_name"))
    op.create_index("ix_achievements_guild_id", "achievements", ["guild_id"])
    op.create_table("user_achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("achievement_id", sa.Integer(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"))
    op.create_index("ix_user_achievements_guild_id", "user_achievements", ["guild_id"])
    op.create_table("quests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("quest_type", sa.String(20), nullable=False, server_default="daily"), sa.Column("condition_type", sa.String(50), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False, server_default="1"), sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"), sa.Column("reward_money", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_participants", sa.Integer(), nullable=True), sa.Column("deadline", sa.DateTime(timezone=True), nullable=True), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("guild_id", "name", name="uq_quest_guild_name"))
    op.create_index("ix_quests_guild_id", "quests", ["guild_id"])
    op.create_table("quest_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("quest_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("progress", sa.Integer(), nullable=False, server_default="0"), sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("quest_id", "user_id", name="uq_quest_progress"))
    op.create_index("ix_quest_progress_guild_id", "quest_progress", ["guild_id"])
    op.create_table("seasons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("start_at", sa.DateTime(timezone=True), nullable=False), sa.Column("end_at", sa.DateTime(timezone=True), nullable=False), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_seasons_guild_id", "seasons", ["guild_id"])
    op.create_table("season_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("season_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("xp", sa.Integer(), nullable=False, server_default="0"), sa.Column("points", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("season_id", "user_id", name="uq_season_progress"))
    op.create_index("ix_season_progress_guild_id", "season_progress", ["guild_id"])
    op.create_table("family_pass",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("season_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("xp", sa.Integer(), nullable=False, server_default="0"), sa.Column("level", sa.Integer(), nullable=False, server_default="0"), sa.Column("claimed_levels", sa.JSON(), nullable=False, server_default="[]"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("season_id", "user_id", name="uq_family_pass"))
    op.create_index("ix_family_pass_guild_id", "family_pass", ["guild_id"])
    op.create_table("family_pass_rewards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("season_id", sa.Integer(), nullable=False), sa.Column("level", sa.Integer(), nullable=False), sa.Column("reward_type", sa.String(30), nullable=False), sa.Column("reward_value", sa.String(200), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("season_id", "level", name="uq_family_pass_reward"))
    op.create_index("ix_family_pass_rewards_guild_id", "family_pass_rewards", ["guild_id"])

    op.create_table("economy_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("bank_balance", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("daily_streak", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_daily", sa.String(10), nullable=True), sa.Column("last_weekly", sa.String(10), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("guild_id", "user_id", name="uq_economy_account"))
    op.create_index("ix_economy_accounts_guild_id", "economy_accounts", ["guild_id"])
    op.create_table("transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("from_user_id", sa.Integer(), nullable=True), sa.Column("to_user_id", sa.Integer(), nullable=True), sa.Column("amount", sa.BigInteger(), nullable=False), sa.Column("transaction_type", sa.String(30), nullable=False), sa.Column("reason", sa.String(200), nullable=False), sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_transactions_guild_id", "transactions", ["guild_id"])
    op.create_table("shop_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("price", sa.BigInteger(), nullable=False), sa.Column("item_type", sa.String(30), nullable=False, server_default="item"), sa.Column("item_value", sa.String(200), nullable=False, server_default=""), sa.Column("stock", sa.Integer(), nullable=True), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("guild_id", "name", name="uq_shop_item_guild_name"))
    op.create_index("ix_shop_items_guild_id", "shop_items", ["guild_id"])
    op.create_table("inventory",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("item_id", sa.Integer(), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("user_id", "item_id", name="uq_inventory_user_item"))
    op.create_index("ix_inventory_guild_id", "inventory", ["guild_id"])
    op.create_table("cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("price", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_cases_guild_id", "cases", ["guild_id"])
    op.create_table("case_rewards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("case_id", sa.Integer(), nullable=False), sa.Column("reward_type", sa.String(30), nullable=False), sa.Column("reward_value", sa.String(200), nullable=False), sa.Column("weight", sa.Integer(), nullable=False, server_default="1"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("family_bank",
        sa.Column("guild_id", sa.BigInteger(), primary_key=True), sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    for table in ["family_bank", "case_rewards", "cases", "inventory", "shop_items", "transactions", "economy_accounts", "family_pass_rewards", "family_pass", "season_progress", "seasons", "quest_progress", "quests", "user_achievements", "achievements"]:
        op.drop_table(table)
