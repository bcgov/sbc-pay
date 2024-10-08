"""new rs status and error codes

Revision ID: f841ac43e15e
Revises: 10fa4c64f1da
Create Date: 2021-08-18 22:47:48.062284

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "f841ac43e15e"
down_revision = "10fa4c64f1da"
branch_labels = None
depends_on = None


def upgrade():
    rs_status_table = table(
        "routing_slip_status_codes",
        column("code", sa.String),
        column("description", sa.String),
    )
    op.bulk_insert(
        rs_status_table,
        [
            {"code": "LINKED", "description": "Linked"},
        ],
    )

    error_code_table = table(
        "error_codes",
        column("code", String),
        column("title", String),
        column("detail", String),
    )

    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "RS_ALREADY_A_PARENT",
                "title": "Routing Slip is already a parent.",
                "detail": "Linking cannot be performed since the routing is already a parent.",
            },
            {
                "code": "RS_ALREADY_LINKED",
                "title": "Routing Slip is already has a parent.",
                "detail": "Linking cannot be performed since the routing already has a parent.",
            },
            {
                "code": "RS_CANT_LINK_TO_SAME",
                "title": "Cant self link.",
                "detail": "Linking to self is not allowed.",
            },
            {
                "code": "RS_CHILD_HAS_TRANSACTIONS",
                "title": "Routing Slip has transactions.",
                "detail": "Linking cannot be performed since the routing slip has transactions.",
            },
            {
                "code": "RS_PARENT_ALREADY_LINKED",
                "title": "Parent Routing Slip is already linked",
                "detail": "Linking cannot be performed since the parent routing is already linked.",
            },
        ],
    )


def downgrade():
    op.execute("DELETE FROM routing_slip_status_codes where code='LINKED'")

    op.execute(
        "DELETE FROM error_codes where code in ('RS_ALREADY_A_PARENT',"
        "'RS_ALREADY_LINKED','RS_CANT_LINK_TO_SAME','RS_PARENT_ALREADY_LINKED', 'RS_CHILD_HAS_TRANSACTIONS')"
    )
