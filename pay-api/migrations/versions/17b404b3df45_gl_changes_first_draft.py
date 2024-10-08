"""gl_changes_first_draft

Revision ID: 17b404b3df45
Revises: 8082a6c00fd7
Create Date: 2020-06-03 16:41:58.666222

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "17b404b3df45"
down_revision = "8082a6c00fd7"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "corp_type", sa.Column("gl_memo", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "corp_type", sa.Column("service_gl_memo", sa.String(length=50), nullable=True)
    )
    op.execute(
        "update corp_type set gl_memo='CO-OP Filing', service_gl_memo='CO-OP Filing' where code='CP'"
    )
    op.execute(
        "update corp_type set gl_memo='BC Registries', service_gl_memo='BC Registries' where code='BC'"
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("corp_type", "service_gl_memo")
    op.drop_column("corp_type", "gl_memo")
    # ### end Alembic commands ###
