"""Adding in cas_version_suffix. This will allow us to recreate routing slips in CAS.

Revision ID: 5418ad1a5fdd
Revises: 833b83dc67ac
Create Date: 2022-12-07 12:42:28.039980

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5418ad1a5fdd"
down_revision = "833b83dc67ac"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "routing_slips", sa.Column("cas_version_suffix", sa.Integer(), nullable=True)
    )
    op.execute(
        "insert into routing_slip_status_codes (code, description) values ('VOID','Voided')"
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("routing_slips", "cas_version_suffix")
    op.execute("delete from routing_slip_status_codes where code = 'VOID';")
    # ### end Alembic commands ###
