"""Compatibility revision for the original Stage 3 database revision name.

This is intentionally a no-op. Some deployed Stage 3 databases were stamped with
0003_stage3_quests_achievements_seasons even though the source revision was later
standardized to 0003_stage3. Keeping this compatibility node lets both databases
upgrade to the same Stage 4 head without changing existing data.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_stage3_quests_achievements_seasons"
down_revision: Union[str, None] = "0003_stage3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
