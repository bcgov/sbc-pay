"""GST data model changes

Revision ID: 38045c22fe00
Revises: 94ca57d30196
Create Date: 2025-07-30 13:31:53.800120

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '38045c22fe00'
down_revision = '94ca57d30196'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('tax_rates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tax_type', sa.String(length=10), nullable=False, comment="Tax type such as 'gst', 'pst'"),
    sa.Column('rate', sa.Numeric(precision=6, scale=4), nullable=False, comment='Tax rate as decimal, e.g. 0.0500 for 5%'),
    sa.Column('start_date', sa.DateTime(timezone=True), nullable=False, comment='When this tax rate becomes effective'),
    sa.Column('effective_end_date', sa.DateTime(timezone=True), nullable=True, comment='When this tax rate expires'),
    sa.Column('description', sa.String(length=200), nullable=True, comment='Description of the tax rate'),
    sa.Column('updated_by', sa.String(length=50), nullable=False),
    sa.Column('updated_name', sa.String(length=50), nullable=False),
    sa.Column('version', sa.Integer(), autoincrement=False, nullable=False, server_default='1'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('tax_rates_history',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('tax_type', sa.String(length=10), autoincrement=False, nullable=False, comment="Tax type such as 'gst', 'pst'"),
    sa.Column('rate', sa.Numeric(precision=6, scale=4), autoincrement=False, nullable=False, comment='Tax rate as decimal, e.g. 0.0500 for 5%'),
    sa.Column('start_date', sa.DateTime(timezone=True), autoincrement=False, nullable=False, comment='When this tax rate becomes effective'),
    sa.Column('effective_end_date', sa.DateTime(timezone=True), autoincrement=False, nullable=True, comment='When this tax rate expires'),
    sa.Column('description', sa.String(length=200), autoincrement=False, nullable=True, comment='Description of the tax rate'),
    sa.Column('updated_by', sa.String(length=50), nullable=False),
    sa.Column('updated_name', sa.String(length=50), nullable=False),
    sa.Column('version', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('changed', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id', 'version'),
    sqlite_autoincrement=True
    )

    with op.batch_alter_table('distribution_codes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('statutory_fees_gst_distribution_code_id', sa.Integer(), nullable=True, comment='Distribution code for GST on statutory fees'))
        batch_op.add_column(sa.Column('service_fee_gst_distribution_code_id', sa.Integer(), nullable=True, comment='Distribution code for GST on service fees'))
        batch_op.create_foreign_key(None, 'distribution_codes', ['service_fee_gst_distribution_code_id'], ['distribution_code_id'])
        batch_op.create_foreign_key(None, 'distribution_codes', ['statutory_fees_gst_distribution_code_id'], ['distribution_code_id'])

    with op.batch_alter_table('distribution_codes_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('statutory_fees_gst_distribution_code_id', sa.Integer(), autoincrement=False, nullable=True, comment='Distribution code for GST on statutory fees'))
        batch_op.add_column(sa.Column('service_fee_gst_distribution_code_id', sa.Integer(), autoincrement=False, nullable=True, comment='Distribution code for GST on service fees'))

    with op.batch_alter_table('fee_schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enable_gst', sa.Boolean(), nullable=True, comment='Flag to indicate if GST should be calculated for this fee schedule'))

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gst', sa.Numeric(precision=19, scale=2), nullable=True, comment='Total GST amount including statutory and service fees GST'))

    with op.batch_alter_table('payment_line_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('statutory_fees_gst', sa.Numeric(precision=19, scale=2), nullable=True, comment='GST for statutory fees (filing_fees)'))
        batch_op.add_column(sa.Column('service_fees_gst', sa.Numeric(precision=19, scale=2), nullable=True, comment='GST for service fees'))


def downgrade():
    with op.batch_alter_table('payment_line_items', schema=None) as batch_op:
        batch_op.drop_column('service_fees_gst')
        batch_op.drop_column('statutory_fees_gst')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('gst')

    with op.batch_alter_table('fee_schedules', schema=None) as batch_op:
        batch_op.drop_column('enable_gst')

    with op.batch_alter_table('distribution_codes_history', schema=None) as batch_op:
        batch_op.drop_column('service_fee_gst_distribution_code_id')
        batch_op.drop_column('statutory_fees_gst_distribution_code_id')

    with op.batch_alter_table('distribution_codes', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('service_fee_gst_distribution_code_id')
        batch_op.drop_column('statutory_fees_gst_distribution_code_id')

    op.drop_table('tax_rates_history')
    op.drop_table('tax_rates')
