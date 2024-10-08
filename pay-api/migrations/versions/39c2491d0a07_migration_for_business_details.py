"""Update details to include the label + business identifier.

Revision ID: 39c2491d0a07
Revises: fd5c02bb9e01
Create Date: 2023-01-12 15:24:43.729871

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "39c2491d0a07"
down_revision = "fd5c02bb9e01"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "update invoices set details = json_build_array(json_build_object('key', 'Registration Number:', 'value', business_identifier)) where (corp_type_code = 'SP' or corp_type_code = 'GP') and details = 'null' and business_identifier is not null"
    )
    op.execute(
        "update invoices set details = json_build_array(json_build_object('key', 'Incorporation Number:', 'value', business_identifier)) where corp_type_code in (select code from corp_types where product = 'BUSINESS' and code <> 'NRO') and details = 'null' and business_identifier is not null"
    )
    pass


def downgrade():
    pass
