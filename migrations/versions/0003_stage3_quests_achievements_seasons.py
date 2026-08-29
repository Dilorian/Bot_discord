"""stage 3: quests, quest_progress, achievements, user_achievements, seasons,
season_progress, family_pass_rewards, family_pass_claims

Revision ID: 0003_stage3
Revises: 0002_stage2
Create Date: 2026-08-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_stage3"
down_revision: Union[str, None] = "0002_stage2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- quests ---
    op.create_table(
        "quests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("quest_type", sa.String(length=20), nullable=False, server_default="individual"),
        sa.Column("requirement_type", sa.String(length=30), nullable=False),
        sa.Column("requirement_amount", sa.Integer(), nullable=False),
        sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_money", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_case", sa.String(length=100), nullable=True),
        sa.Column("max_participants", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_quests_guild_id", "quests", ["guild_id"])

    # --- quest_progress ---
    op.create_table(
        "quest_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("progress_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_claimed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("quest_id", "discord_id", name="uq_quest_progress_user"),
    )
    op.create_index("ix_quest_progress_guild_id", "quest_progress", ["guild_id"])
    op.create_index("ix_quest_progress_discord_id", "quest_progress", ["discord_id"])

    # --- achievements ---
    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("rarity", sa.String(length=20), nullable=False, server_default="common"),
        sa.Column("requirement_type", sa.String(length=30), nullable=False),
        sa.Column("requirement_amount", sa.Integer(), nullable=False),
        sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_title", sa.String(length=100), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guild_id", "key", name="uq_achievement_guild_key"),
    )
    op.create_index("ix_achievements_guild_id", "achievements", ["guild_id"])

    # --- user_achievements ---
    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "achievement_id", sa.Integer(), sa.ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("discord_id", "achievement_id", name="uq_user_achievement"),
    )
    op.create_index("ix_user_achievements_guild_id", "user_achievements", ["guild_id"])
    op.create_index("ix_user_achievements_discord_id", "user_achievements", ["discord_id"])

    # --- seasons ---
    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_seasons_guild_id", "seasons", ["guild_id"])

    # --- season_progress ---
    op.create_table(
        "season_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("season_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pass_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("season_id", "discord_id", name="uq_season_progress_user"),
    )
    op.create_index("ix_season_progress_guild_id", "season_progress", ["guild_id"])
    op.create_index("ix_season_progress_discord_id", "season_progress", ["discord_id"])

    # --- family_pass_rewards ---
    op.create_table(
        "family_pass_rewards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("reward_type", sa.String(length=30), nullable=False),
        sa.Column("reward_value", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("season_id", "level_number", name="uq_family_pass_reward_level"),
    )
    op.create_index("ix_family_pass_rewards_guild_id", "family_pass_rewards", ["guild_id"])

    # --- family_pass_claims ---
    op.create_table(
        "family_pass_claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("season_id", "discord_id", "level_number", name="uq_family_pass_claim"),
    )
    op.create_index("ix_family_pass_claims_guild_id", "family_pass_claims", ["guild_id"])
    op.create_index("ix_family_pass_claims_discord_id", "family_pass_claims", ["discord_id"])


def downgrade() -> None:
    op.drop_table("family_pass_claims")
    op.drop_table("family_pass_rewards")
    op.drop_table("season_progress")
    op.drop_table("seasons")
    op.drop_table("user_achievements")
    op.drop_table("achievements")
    op.drop_table("quest_progress")
    op.drop_table("quests")
