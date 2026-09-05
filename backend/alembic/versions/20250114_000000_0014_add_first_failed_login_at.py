"""Add first_failed_login_at to users for sliding-window account lockout.

The account-lockout logic locks after N failed attempts within a time window
(account_lockout_window_minutes). The window is anchored by the timestamp of
the first failure in the current streak, so a dedicated nullable column is
required. NULL means there is no active failure window.

Revision ID: 0014
Revises: 0013
Create Date: 2025-01-14 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "first_failed_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Timestamp of the first failed login in the current lockout "
                "window (NULL when no active window); anchors the "
                "sliding-window lockout"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "first_failed_login_at")
