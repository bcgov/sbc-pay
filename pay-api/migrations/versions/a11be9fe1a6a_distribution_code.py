"""empty message

Revision ID: a11be9fe1a6a
Revises: cf9a60955b68
Create Date: 2020-07-27 10:33:34.602674

"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "a11be9fe1a6a"
down_revision = "cf9a60955b68"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    distribution_code_table = op.create_table(
        "distribution_code",
        sa.Column("created_on", sa.DateTime(), nullable=False),
        sa.Column("updated_on", sa.DateTime(), nullable=True),
        sa.Column(
            "distribution_code_id", sa.Integer(), autoincrement=True, nullable=False
        ),
        sa.Column("memo_name", sa.String(length=50), nullable=True),
        sa.Column("service_fee_memo_name", sa.String(length=50), nullable=True),
        sa.Column("client", sa.String(length=50), nullable=True),
        sa.Column("responsibility_centre", sa.String(length=50), nullable=True),
        sa.Column("service_line", sa.String(length=50), nullable=True),
        sa.Column("stob", sa.String(length=50), nullable=True),
        sa.Column("project_code", sa.String(length=50), nullable=True),
        sa.Column("service_fee_client", sa.String(length=50), nullable=True),
        sa.Column(
            "service_fee_responsibility_centre", sa.String(length=50), nullable=True
        ),
        sa.Column("service_fee_line", sa.String(length=50), nullable=True),
        sa.Column("service_fee_stob", sa.String(length=50), nullable=True),
        sa.Column("service_fee_project_code", sa.String(length=50), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_by", sa.String(length=50), nullable=False),
        sa.Column("created_name", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
        sa.Column("updated_name", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("distribution_code_id"),
    )

    distribution_code_link_table = op.create_table(
        "distribution_code_link",
        sa.Column("distribution_link_id", sa.Integer(), nullable=False),
        sa.Column("fee_schedule_id", sa.Integer(), nullable=True),
        sa.Column("distribution_code_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["distribution_code_id"],
            ["distribution_code.distribution_code_id"],
        ),
        sa.ForeignKeyConstraint(
            ["fee_schedule_id"],
            ["fee_schedule.fee_schedule_id"],
        ),
        sa.PrimaryKeyConstraint("distribution_link_id"),
    )
    op.add_column(
        "fee_schedule",
        sa.Column("service_fee_code", sa.String(length=10), nullable=True),
    )
    op.create_foreign_key(
        "service_fee_code_fk",
        "fee_schedule",
        "fee_code",
        ["service_fee_code"],
        ["code"],
    )
    op.add_column(
        "payment_line_item",
        sa.Column("fee_distribution_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "payment_line_item", sa.Column("service_fees", sa.Float(), nullable=True)
    )
    op.create_foreign_key(
        "fee_distribution_id_fk",
        "payment_line_item",
        "distribution_code",
        ["fee_distribution_id"],
        ["distribution_code_id"],
    )

    # Insert records from corp_type to distribution_code and create a link with fee_schedule
    op.bulk_insert(
        distribution_code_table,
        [
            {
                "distribution_code_id": 1,
                "created_by": "Alembic",
                "created_on": datetime.now(tz=timezone.utc),
                "memo_name": "CO-OP Filing",
                "service_fee_memo_name": None,
                "start_date": datetime.now(tz=timezone.utc),
            },
            {
                "distribution_code_id": 2,
                "created_by": "Alembic",
                "created_on": datetime.now(tz=timezone.utc),
                "memo_name": "Benefit Companies",
                "service_fee_memo_name": "SBC Modernization Service Charge",
                "start_date": datetime.now(tz=timezone.utc),
            },
            {
                "distribution_code_id": 3,
                "created_by": "Alembic",
                "created_on": datetime.now(tz=timezone.utc),
                "memo_name": "Benefit Companies",
                "service_fee_memo_name": "SBC Modernization Service Charge",
                "start_date": datetime.now(tz=timezone.utc),
            },
            {
                "distribution_code_id": 4,
                "created_by": "Alembic",
                "created_on": datetime.now(tz=timezone.utc),
                "memo_name": "VS",
                "service_fee_memo_name": "SBC Modernization Service Charge",
                "start_date": datetime.now(tz=timezone.utc),
            },
            {
                "distribution_code_id": 5,
                "created_by": "Alembic",
                "created_on": datetime.now(tz=timezone.utc),
                "memo_name": "PPR",
                "service_fee_memo_name": "SBC Modernization Service Charge",
                "start_date": datetime.now(tz=timezone.utc),
            },
        ],
    )

    conn = op.get_bind()
    res = conn.execute(
        sa.text("select fee_schedule_id, corp_type_code from fee_schedule;")
    )
    results = res.fetchall()
    for result in results:
        distribution_code_id = None
        corp_type_code = result[1]

        if corp_type_code == "CP":
            distribution_code_id = 1
        elif corp_type_code == "BC":
            distribution_code_id = 2
        elif corp_type_code == "NRO":
            distribution_code_id = 3
        elif corp_type_code == "VS":
            distribution_code_id = 4
        elif corp_type_code == "PPR":
            distribution_code_id = 5

        op.bulk_insert(
            distribution_code_link_table,
            [
                {
                    "distribution_code_id": distribution_code_id,
                    "fee_schedule_id": result[0],
                }
            ],
        )

        # Update all payment line item which used this fee schedule with distribution_code_id
        op.execute(
            "update payment_line_item set fee_distribution_id={} where fee_schedule_id={};".format(
                distribution_code_id, result[0]
            )
        )
    # Update service fee codes for fee schedule
    op.execute(
        "update fee_schedule set service_fee_code='TRF01' where corp_type_code in ('BC', 'VS', 'PPR', 'NRO')"
    )

    # Above script creates 5 default entries, so reset the sequence to 6.
    op.execute(
        "ALTER SEQUENCE distribution_code_distribution_code_id_seq RESTART WITH 6"
    )
    ## Insert complete

    op.drop_constraint(
        "corp_type_transaction_fee_code_fkey", "corp_type", type_="foreignkey"
    )
    op.drop_column("corp_type", "gl_memo")
    op.drop_column("corp_type", "service_fee_code")
    op.drop_column("corp_type", "service_gl_memo")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "fee_distribution_id_fk", "payment_line_item", type_="foreignkey"
    )
    op.drop_column("payment_line_item", "service_fees")
    op.drop_column("payment_line_item", "fee_distribution_id")
    op.drop_constraint("service_fee_code_fk", "fee_schedule", type_="foreignkey")
    op.drop_column("fee_schedule", "service_fee_code")
    op.add_column(
        "corp_type",
        sa.Column(
            "service_gl_memo", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "corp_type",
        sa.Column(
            "service_fee_code",
            sa.VARCHAR(length=10),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "corp_type",
        sa.Column("gl_memo", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(
        "corp_type_transaction_fee_code_fkey",
        "corp_type",
        "fee_code",
        ["service_fee_code"],
        ["code"],
    )
    op.drop_table("distribution_code_link")
    op.drop_table("distribution_code")
    # ### end Alembic commands ###
