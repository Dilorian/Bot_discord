"""stage 2: profiles, xp_history, levels, reputation_history + xp settings columns

Revision ID: 0002_stage2
Revises: 0001_initial
Create Date: 2026-08-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_stage2"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- новые настройки XP на существующей таблице settings ---
    op.add_column("settings", sa.Column("xp_message_min", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("settings", sa.Column("xp_message_max", sa.Integer(), nullable=False, server_default="15"))
    op.add_column(
        "settings",
        sa.Column("xp_message_cooldown_seconds", sa.Integer(), nullable=False, server_default="60"),
    )
    op.add_column("settings", sa.Column("xp_voice_per_minute", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("settings", sa.Column("xp_daily_cap", sa.Integer(), nullable=True))
    op.add_column(
        "settings",
        sa.Column("xp_disabled_channels", sa.JSON(), nullable=False, server_default="[]"),
    )

    # --- profiles ---
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("game_nickname", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("total_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reputation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voice_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activity_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_activity_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_profiles_user_id"),
    )
    op.create_index("ix_profiles_guild_id", "profiles", ["guild_id"])

    # --- xp_history ---
    op.create_table(
        "xp_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("actor_discord_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_xp_history_guild_id", "xp_history", ["guild_id"])
    op.create_index("ix_xp_history_discord_id", "xp_history", ["discord_id"])

    # --- levels ---
    op.create_table(
        "levels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("reward_role_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "level_number", name="uq_level_guild_number"),
    )
    op.create_index("ix_levels_guild_id", "levels", ["guild_id"])

    # --- reputation_history ---
    op.create_table(
        "reputation_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("change", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("actor_discord_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reputation_history_guild_id", "reputation_history", ["guild_id"])
    op.create_index("ix_reputation_history_discord_id", "reputation_history", ["discord_id"])


def downgrade() -> None:
    op.drop_table("reputation_history")
    op.drop_table("levels")
    op.drop_table("xp_history")
    op.drop_index("ix_profiles_guild_id", table_name="profiles")
    op.drop_table("profiles")

    op.drop_column("settings", "xp_disabled_channels")
    op.drop_column("settings", "xp_daily_cap")
    op.drop_column("settings", "xp_voice_per_minute")
    op.drop_column("settings", "xp_message_cooldown_seconds")
    op.drop_column("settings", "xp_message_max")
    op.drop_column("settings", "xp_message_min")
