"""fix_payment_account_id_in_payment_table

Revision ID: 331c2cdb0b94
Revises: 0449261c3fa7
Create Date: 2020-12-08 09:59:41.540905

"""

import base64

import sqlalchemy as sa
from alembic import op
from flask import current_app
from sqlalchemy import Integer, String
from sqlalchemy.sql import column, table

from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import AuthHeaderType, ContentType


# revision identifiers, used by Alembic.
revision = "331c2cdb0b94"
down_revision = "0449261c3fa7"
branch_labels = None
depends_on = None


def upgrade():
    """Update payment records with null account id."""
    # 1. Find all payments with account id null
    # 2. Find the account id from invoice table linking with invoice_reference table.
    # 3. Update payment with payment account id.
    conn = op.get_bind()
    res = conn.execute(
        sa.text(
            f"select id,invoice_number from payment where payment_account_id is null;"
        )
    )
    results = res.fetchall()
    for result in results:
        pay_id = result[0]
        invoice_number = result[1]
        res = conn.execute(
            sa.text(
                f"select payment_account_id from invoice where id=(select invoice_id from invoice_reference where invoice_number='{invoice_number}');"
            )
        )
        payment_account_id_result = res.fetchall()
        if payment_account_id_result:
            payment_account_id = payment_account_id_result[0][0]
            op.execute(
                f"update payment set payment_account_id={payment_account_id} where id = {pay_id}"
            )


def downgrade():
    pass
