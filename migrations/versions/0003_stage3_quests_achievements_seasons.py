"""Compatibility alias for databases deployed with the long Stage 3 revision ID.

Revision ID: 0003_stage3_quests_achievements_seasons
Revises: 0003_stage3
"""
from typing import Sequence, Union
from alembic import op
revision: str = "0003_stage3_quests_achievements_seasons"
down_revision: Union[str, None] = "0003_stage3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None: pass
def downgrade() -> None: pass
