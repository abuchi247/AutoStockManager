"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Revision identifiers used by Alembic to maintain migration ordering.
# 'revision' is the unique ID of this migration.
# 'down_revision' links to the previous migration (None for the first migration).
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Apply forward schema changes.

    This function is executed when running 'alembic upgrade'.
    Add your CREATE TABLE, ALTER TABLE, CREATE INDEX, etc. operations here.
    """
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revert schema changes applied by upgrade().

    This function is executed when running 'alembic downgrade'.
    It should exactly reverse the operations performed in upgrade().
    """
    ${downgrades if downgrades else "pass"}
