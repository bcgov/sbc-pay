"""CAS settlements, plus adding ack_file_ref to EJV files.
This will get rid of issues where the queue sends over duplicate messages over a period of time.

Revision ID: 9abc5b5245b6
Revises: bf3f354aa6ad
Create Date: 2022-10-03 10:38:53.597618

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9abc5b5245b6'
down_revision = 'bf3f354aa6ad'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('cas_settlements',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('received_on', sa.DateTime(), nullable=False),
    sa.Column('file_name', sa.String(), nullable=False),
    sa.Column('processed_on', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('ejv_files', sa.Column('ack_file_ref', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ejv_files', 'ack_file_ref')
    op.drop_table('cas_settlements')
    # ### end Alembic commands ###
