"""seed entity types

Revision ID: f213dea27381
Revises: d68ec6d60d0d
Create Date: (auto generated)

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f213dea27381"
down_revision: Union[str, Sequence[str], None] = "d68ec6d60d0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed default entity types."""
    op.bulk_insert(
        sa.table(
            "entity_types",
            sa.column("name", sa.String),
            sa.column("is_default", sa.Boolean),
        ),
        [
            {"name": "home",     "is_default": True},
            {"name": "work",     "is_default": True},
            {"name": "business", "is_default": True},
            {"name": "other",    "is_default": True},
        ]
    )


def downgrade() -> None:
    """Remove seeded entity types."""
    op.execute("DELETE FROM entity_types WHERE is_default = 1")