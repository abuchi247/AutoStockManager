"""Add must_change_password column to users table.

Supports forced password change on first login for auto-provisioned
and admin-created accounts.

Revision ID: 0008
Revises: 0007
Create Date: 2025-01-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("users")
    }
    if "must_change_password" not in existing_columns:
        op.add_column(
            "users",
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                nullable=False,
                server_default="false",
                comment="If true, the user must change their password before accessing the system",
            ),
        )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
