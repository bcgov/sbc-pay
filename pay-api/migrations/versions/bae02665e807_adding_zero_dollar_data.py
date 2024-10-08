"""adding_zero_dollar_data

Revision ID: bae02665e807
Revises: 2d75a53b0cbd
Create Date: 2019-09-27 10:56:24.379903

"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Date, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "bae02665e807"
down_revision = "2d75a53b0cbd"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "payment_transaction",
        "client_system_url",
        existing_type=sa.VARCHAR(length=500),
        nullable=True,
    )

    op.create_index(
        op.f("ix_invoice_invoice_number"), "invoice", ["invoice_number"], unique=False
    )

    payment_system_table = table(
        "payment_system", column("code", String), column("description", String)
    )

    filing_type_table = table(
        "filing_type", column("code", String), column("description", String)
    )
    fee_schedule_table = table(
        "fee_schedule",
        column("filing_type_code", String),
        column("corp_type_code", String),
        column("fee_code", String),
        column("fee_start_date", Date),
        column("fee_end_date", Date),
    )

    op.bulk_insert(
        payment_system_table,
        [{"code": "INTERNAL", "description": "Payments handled internally"}],
    )

    op.bulk_insert(
        filing_type_table, [{"code": "OTFDR", "description": "Change of Director"}]
    )

    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "OTFDR",
                "corp_type_code": "CP",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            }
        ],
    )


def downgrade():
    op.execute("DELETE FROM fee_schedule WHERE filing_type_code = 'OTFDR';")
    op.execute("DELETE FROM filing_type WHERE code = 'OTFDR';")
    op.execute("DELETE FROM payment_system WHERE code = 'INTERNAL';")

    op.alter_column(
        "payment_transaction",
        "client_system_url",
        existing_type=sa.VARCHAR(length=500),
        nullable=False,
    )
    op.drop_index(op.f("ix_invoice_invoice_number"), table_name="invoice")
