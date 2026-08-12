"""Add phones and bank_accounts JSONB arrays to business_settings.

Replaces the single scalar phone / bank_* columns with JSONB arrays that
support an arbitrary number of phone numbers and bank accounts.

The legacy scalar columns are kept (nullable) so that a downgrade can
restore data without loss. The upgrade step copies any existing scalar
values into the new arrays before the application starts using them.

Revision ID: 0009
Revises: 0008
Create Date: 2025-01-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add the two new JSONB columns.
    #    server_default must be expressed as sa.text() so Alembic emits the
    #    literal SQL fragment  DEFAULT '[]'::jsonb  without extra quoting.
    op.add_column(
        "business_settings",
        sa.Column(
            "phones",
            JSONB,
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
            comment='[{"label":"Main","number":"08012345678"}]',
        ),
    )
    op.add_column(
        "business_settings",
        sa.Column(
            "bank_accounts",
            JSONB,
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
            comment='[{"bank_name":"...","account_number":"...","account_name":"..."}]',
        ),
    )

    # 2. Migrate any existing scalar data into the arrays.
    #    Only touch rows where the scalar columns actually have values.
    op.execute(
        """
        UPDATE business_settings
        SET phones = CASE
            WHEN phone IS NOT NULL AND phone <> ''
            THEN jsonb_build_array(
                     jsonb_build_object('label', 'Main', 'number', phone)
                 )
            ELSE '[]'::jsonb
        END
        WHERE phones IS NULL OR phones = '[]'::jsonb
        """
    )

    op.execute(
        """
        UPDATE business_settings
        SET bank_accounts = CASE
            WHEN bank_name IS NOT NULL AND bank_name <> ''
            THEN jsonb_build_array(
                     jsonb_build_object(
                         'bank_name',       COALESCE(bank_name, ''),
                         'account_number',  COALESCE(bank_account_number, ''),
                         'account_name',    COALESCE(bank_account_name, '')
                     )
                 )
            ELSE '[]'::jsonb
        END
        WHERE bank_accounts IS NULL OR bank_accounts = '[]'::jsonb
        """
    )


def downgrade() -> None:
    # Copy the first element of each array back into the scalar columns so
    # that rolling back to 0008 does not lose the primary contact/account.
    op.execute(
        """
        UPDATE business_settings
        SET phone = (phones -> 0 ->> 'number')
        WHERE phones IS NOT NULL
          AND jsonb_array_length(phones) > 0
          AND (phone IS NULL OR phone = '')
        """
    )

    op.execute(
        """
        UPDATE business_settings
        SET bank_name           = (bank_accounts -> 0 ->> 'bank_name'),
            bank_account_number = (bank_accounts -> 0 ->> 'account_number'),
            bank_account_name   = (bank_accounts -> 0 ->> 'account_name')
        WHERE bank_accounts IS NOT NULL
          AND jsonb_array_length(bank_accounts) > 0
          AND (bank_name IS NULL OR bank_name = '')
        """
    )

    op.drop_column("business_settings", "bank_accounts")
    op.drop_column("business_settings", "phones")
