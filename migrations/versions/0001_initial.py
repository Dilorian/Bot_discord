"""initial stage 1 tables: users, ranks, rank_permissions, settings, bot_logs, audit_logs

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ranks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("discord_role_id", sa.BigInteger(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "name", name="uq_rank_guild_name"),
    )
    op.create_index("ix_ranks_guild_id", "ranks", ["guild_id"])

    op.create_table(
        "rank_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("rank_id", sa.Integer(), sa.ForeignKey("ranks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_key", sa.String(length=64), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("rank_id", "permission_key", name="uq_rank_permission"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active_member", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rank_id", sa.Integer(), sa.ForeignKey("ranks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("discord_id", name="uq_users_discord_id"),
    )
    op.create_index("ix_users_discord_id", "users", ["discord_id"])
    op.create_index("ix_users_guild_id", "users", ["guild_id"])

    op.create_table(
        "settings",
        sa.Column("guild_id", sa.BigInteger(), primary_key=True),
        sa.Column("admin_role_id", sa.BigInteger(), nullable=True),
        sa.Column("log_channel_id", sa.BigInteger(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "bot_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_discord_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_guild_id", "audit_logs", ["guild_id"])
    op.create_index("ix_audit_logs_actor_discord_id", "audit_logs", ["actor_discord_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("bot_logs")
    op.drop_table("settings")
    op.drop_index("ix_users_guild_id", table_name="users")
    op.drop_index("ix_users_discord_id", table_name="users")
    op.drop_table("users")
    op.drop_table("rank_permissions")
    op.drop_index("ix_ranks_guild_id", table_name="ranks")
    op.drop_table("ranks")
