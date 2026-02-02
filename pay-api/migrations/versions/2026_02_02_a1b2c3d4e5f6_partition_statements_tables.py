"""Partition statements and statement_invoices tables.

With ~7M statements generated per year, yearly RANGE partitioning on from_date
improves query performance and maintenance operations.

Revision ID: a1b2c3d4e5f6
Revises: f52120aa9993
Create Date: 2026-02-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'f52120aa9993'
branch_labels = None
depends_on = None


def upgrade():
    # Add statement_from to statement_invoices (denormalized for partition alignment)
    op.execute("ALTER TABLE statement_invoices ADD COLUMN statement_from DATE;")
    op.execute("""
        UPDATE statement_invoices si
        SET statement_from = s.from_date
        FROM statements s
        WHERE si.statement_id = s.id;
    """)
    op.execute("ALTER TABLE statement_invoices ALTER COLUMN statement_from SET NOT NULL;")

    op.execute("""
        CREATE TABLE statements_new (
            id SERIAL,
            frequency VARCHAR(50),
            statement_settings_id INTEGER,
            payment_account_id INTEGER,
            from_date DATE NOT NULL,
            to_date DATE,
            is_interim_statement BOOLEAN NOT NULL DEFAULT FALSE,
            is_empty BOOLEAN NOT NULL DEFAULT FALSE,
            overdue_notification_date DATE,
            created_on DATE NOT NULL,
            notification_status_code VARCHAR(20),
            notification_date DATE,
            payment_methods VARCHAR(100),
            PRIMARY KEY (id, from_date)
        ) PARTITION BY RANGE (from_date);
    """)

    op.execute("""
        CREATE TABLE statement_invoices_new (
            id SERIAL,
            statement_id INTEGER NOT NULL,
            invoice_id INTEGER NOT NULL,
            statement_from DATE NOT NULL,
            PRIMARY KEY (id, statement_from)
        ) PARTITION BY RANGE (statement_from);
    """)

    for year in range(2020, 2051):
        op.execute(f"""
            CREATE TABLE statements_{year} PARTITION OF statements_new
            FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01');
        """)
        op.execute(f"""
            CREATE TABLE statement_invoices_{year} PARTITION OF statement_invoices_new
            FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01');
        """)

    # Create default partitions for dates outside range
    op.execute("CREATE TABLE statements_default PARTITION OF statements_new DEFAULT;")
    op.execute("CREATE TABLE statement_invoices_default PARTITION OF statement_invoices_new DEFAULT;")

    op.execute("""
        INSERT INTO statements_new (
            id, frequency, statement_settings_id, payment_account_id,
            from_date, to_date, is_interim_statement, is_empty, overdue_notification_date,
            created_on, notification_status_code, notification_date, payment_methods
        )
        SELECT
            s.id, s.frequency, s.statement_settings_id, s.payment_account_id,
            s.from_date, s.to_date, s.is_interim_statement,
            NOT EXISTS (SELECT 1 FROM statement_invoices si WHERE si.statement_id = s.id),
            s.overdue_notification_date, s.created_on, s.notification_status_code,
            s.notification_date, s.payment_methods
        FROM statements s;
    """)
    op.execute("""
        INSERT INTO statement_invoices_new (id, statement_id, invoice_id, statement_from)
        SELECT id, statement_id, invoice_id, statement_from
        FROM statement_invoices;
    """)

    # Swap tables
    op.execute("ALTER TABLE statements RENAME TO statements_old;")
    op.execute("ALTER TABLE statement_invoices RENAME TO statement_invoices_old;")
    op.execute("ALTER TABLE statements_new RENAME TO statements;")
    op.execute("ALTER TABLE statement_invoices_new RENAME TO statement_invoices;")

    op.execute("CREATE INDEX ix_statements_frequency ON statements (frequency);")
    op.execute("CREATE INDEX ix_statements_statement_settings_id ON statements (statement_settings_id);")
    op.execute("CREATE INDEX ix_statements_payment_account_id ON statements (payment_account_id);")
    op.execute("CREATE INDEX ix_statements_created_on ON statements (created_on);")
    op.execute("CREATE INDEX ix_statements_is_empty ON statements (is_empty);")
    op.execute("CREATE INDEX ix_statement_invoices_statement_id ON statement_invoices (statement_id);")
    op.execute("CREATE INDEX ix_statement_invoices_invoice_id ON statement_invoices (invoice_id);")

    op.execute("""
        ALTER TABLE statements
        ADD CONSTRAINT statements_statement_settings_id_fkey
        FOREIGN KEY (statement_settings_id) REFERENCES statement_settings(id);
    """)
    op.execute("""
        ALTER TABLE statements
        ADD CONSTRAINT statements_payment_account_id_fkey
        FOREIGN KEY (payment_account_id) REFERENCES payment_accounts(id);
    """)
    op.execute("""
        ALTER TABLE statements
        ADD CONSTRAINT statements_notification_status_code_fkey
        FOREIGN KEY (notification_status_code) REFERENCES notification_status_codes(code);
    """)
    op.execute("""
        ALTER TABLE statement_invoices
        ADD CONSTRAINT statement_invoices_invoice_id_fkey
        FOREIGN KEY (invoice_id) REFERENCES invoices(id);
    """)

    op.execute("SELECT setval('statements_new_id_seq', (SELECT MAX(id) FROM statements));")
    op.execute("SELECT setval('statement_invoices_new_id_seq', (SELECT MAX(id) FROM statement_invoices));")

    # Drop old tables when ready (commented for safety)
    # op.execute("DROP TABLE statements_old CASCADE;")
    # op.execute("DROP TABLE statement_invoices_old CASCADE;")


def downgrade():
    # Swap back to original tables
    op.execute("ALTER TABLE statements RENAME TO statements_partitioned;")
    op.execute("ALTER TABLE statement_invoices RENAME TO statement_invoices_partitioned;")
    op.execute("ALTER TABLE statements_old RENAME TO statements;")
    op.execute("ALTER TABLE statement_invoices_old RENAME TO statement_invoices;")
    op.execute("ALTER TABLE statement_invoices DROP COLUMN statement_from;")
    op.execute("DROP TABLE IF EXISTS statements_partitioned CASCADE;")
    op.execute("DROP TABLE IF EXISTS statement_invoices_partitioned CASCADE;")
