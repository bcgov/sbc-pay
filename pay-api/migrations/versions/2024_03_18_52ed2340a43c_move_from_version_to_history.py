"""Move data from version to history table.
A special thanks to LEAR devs (Thor, Argus, Vysakh) for this migration and the history table implementation:
https://github.com/bcgov/lear/blob/feature-legal-name/legal-api/scripts/manual_db_scripts/legal_name_change/transfer_to_new_lear.sql

Revision ID: 52ed2340a43c
Revises: fb3ba97b603a
Create Date: 2024-03-18 09:53:33.369110

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "52ed2340a43c"
down_revision = "fb3ba97b603a"
branch_labels = None
depends_on = None


def upgrade():
    # Currently these are only set to version = 1
    op.execute(
        """
               update account_fees set version =
                    (select coalesce(
                        (select count(transaction_id) as version
                            from account_fees_version
                        where 
                            account_fees.id = account_fees_version.id
                        group by
                            id
                    ), 1));
               """
    )

    op.execute(
        """
               update cfs_accounts set version =
                (select coalesce(
               (select count(transaction_id) as version
                    from cfs_accounts_version
                    where cfs_accounts.id = cfs_accounts_version.id
                    group by id
               ), 1));
               """
    )

    op.execute(
        """
               update distribution_codes set version =
               (select coalesce(
               (select count(transaction_id) as version
                    from distribution_codes_version
                    where distribution_codes.distribution_code_id = distribution_codes_version.distribution_code_id
                    group by distribution_code_id
               ),1));
               """
    )

    op.execute(
        """
               update eft_short_names set version =
               (select coalesce(
               (select count(transaction_id) as version
                    from eft_short_names_version
                    where eft_short_names.id = eft_short_names_version.id
                    group by id
               ),1));
               """
    )

    op.execute(
        """
               update payment_accounts set version =
                (select coalesce(
                (select count(transaction_id) as version
                        from payment_accounts_version
                        where payment_accounts.id = payment_accounts_version.id 
                        group by id
                ),1));
               """
    )

    op.execute(
        """
               update refunds_partial set version =
                (select coalesce(
                (select count(transaction_id) as version
                    from refunds_partial_version
                    where refunds_partial.id = refunds_partial_version.id
                    group by id
               ),1));
               """
    )

    op.execute(
        """
        with subquery as (
            select 
                afv.id,
                account_id, 
                apply_filing_fees, 
                service_fee_code, 
                product, 
                created_on, 
                updated_on, 
                created_by, 
                created_name, 
                updated_by, 
                updated_name, 
                t.issued_at as changed, 
                COALESCE(ROW_NUMBER() OVER (PARTITION BY afv.id ORDER BY afv.transaction_id ASC), 1) as version
            from 
                account_fees_version afv 
            left join 
               transaction t on afv.transaction_id = t.id
        ),
        max_versions as (
            select 
                id,
                max(version) as max_version
            from 
               subquery sq
            group by id
        )
               
        insert into 
               account_fees_history (id, apply_filing_fees, service_fee_code, product, created_on, updated_on, 
                                     created_by, created_name, updated_by, updated_name, changed, version) 
        select 
            sq.id, apply_filing_fees, service_fee_code, product, created_on, updated_on, 
                                     created_by, created_name, updated_by, updated_name, changed, version
        from 
            subquery sq
        left join 
            max_versions mv on mv.id = sq.id
        where
               sq.version != mv.max_version;
               """
    )

    op.execute(
        """
        with subquery as (
            select
                cav.id,
                cfs_account,
                cfs_party, 
                cfs_site,
                payment_instrument_number, 
                contact_party, 
                bank_number, 
                bank_branch_number,
                t.issued_at as changed, 
                COALESCE(ROW_NUMBER() OVER (PARTITION BY cav.id ORDER BY cav.transaction_id ASC), 1) as version
            from cfs_accounts_version cav
                left join transaction t on cav.transaction_id = t.id
        ),
        max_versions as (
            select 
                id,
                max(version) as max_version
            from 
                subquery sq
            group by id
        )
        insert into
            cfs_accounts_history (id, cfs_account, cfs_party, cfs_site, payment_instrument_number,
            contact_party, bank_number, bank_branch_number, changed, version)
        select 
            sq.id, cfs_account, cfs_party, cfs_site, payment_instrument_number,
            contact_party, bank_number, bank_branch_number, changed, version
        from 
            subquery sq
        left join 
            max_versions mv on mv.id = sq.id
        where
            sq.version != mv.max_version;
            """
    )

    op.execute(
        """
        with subquery as (
            select
                dcv.distribution_code_id,
                name,
                client,
                responsibility_centre,
                service_line,
                stob,
                project_code,
                start_date,
                end_date,
                stop_ejv,
                service_fee_distribution_code_id,
                disbursement_distribution_code_id,
                account_id,
                created_on,
                updated_on,
                created_by,
                created_name,
                updated_by,
                updated_name,
                t.issued_at as changed,
                COALESCE(ROW_NUMBER() OVER (PARTITION BY dcv.distribution_code_id ORDER BY dcv.transaction_id ASC), 1) as version
            from distribution_codes_version dcv
                left join transaction t on dcv.transaction_id = t.id
        ),
        max_versions as (
            select
                sq.distribution_code_id,
                max(version) as max_version
            from subquery sq
            group by sq.distribution_code_id
        )
        
        insert into 
            distribution_codes_history (distribution_code_id, name, client, responsibility_centre,
            service_line, stob, project_code, start_date, end_date, stop_ejv, service_fee_distribution_code_id,
            disbursement_distribution_code_id, account_id, created_on, updated_on, created_by, created_name,
            updated_by, updated_name, changed, version)
        select 
            sq.distribution_code_id, name, client, responsibility_centre,
            service_line, stob, project_code, start_date, end_date, stop_ejv, service_fee_distribution_code_id,
            disbursement_distribution_code_id, account_id, created_on, updated_on, created_by, created_name,
            updated_by, updated_name, changed, version
        from 
            subquery sq
        left join 
            max_versions mv on mv.distribution_code_id = sq.distribution_code_id
        where sq.version != mv.max_version;
               """
    )

    op.execute(
        """
        with subquery as (
            select
                esnv.id,
                auth_account_id,
                created_on,
                short_name,
                linked_by,
                linked_by_name,
                linked_on,
                t.issued_at as changed,
                COALESCE(ROW_NUMBER() OVER (PARTITION BY esnv.id ORDER BY esnv.transaction_id ASC), 1) as version
            from eft_short_names_version esnv
            left join transaction t on esnv.transaction_id = t.id
        ), 
        max_versions as (
            select 
               id,
               max(version) as max_version
            from
               subquery sq
            group by id
        )
        insert into 
            eft_short_names_history (id, auth_account_id, created_on, short_name, linked_by, linked_by_name, linked_on, changed, version)
        select 
            sq.id, auth_account_id, created_on, short_name, linked_by, linked_by_name, linked_on, changed, version
        from 
            subquery sq
        left join 
            max_versions mv on mv.id = sq.id
        where sq.version != mv.max_version;
               """
    )

    op.execute(
        """
        with subquery as (
            select
                pav.id,
                auth_account_id,
                name,
                branch_name,
                payment_method,
                bcol_user_id,
                bcol_account,
                statement_notification_enabled,
                credit,
                billable,
                eft_enable,
                pad_activation_date,
                pad_tos_accepted_date,
                pad_tos_accepted_by,
                t.issued_at as changed,
                COALESCE(ROW_NUMBER() OVER (PARTITION BY pav.id ORDER BY pav.transaction_id ASC), 1) as version
            from 
               payment_accounts_version pav
            left join 
               transaction t on pav.transaction_id = t.id
            ),
            max_versions as (
                select
                    id,
                    max(version) as max_version
                from
                    subquery sq
                group by id
            )
            insert into
               payment_accounts_history (id, auth_account_id, name, branch_name, payment_method, bcol_user_id,
                    bcol_account, statement_notification_enabled, credit, billable, eft_enable, pad_activation_date,
                    pad_tos_accepted_date, pad_tos_accepted_by, changed, version)
            select
               sq.id, auth_account_id, name, branch_name, payment_method, bcol_user_id,
                    bcol_account, statement_notification_enabled, credit, billable, eft_enable, pad_activation_date,
                    pad_tos_accepted_date, pad_tos_accepted_by, changed, version
            from
               subquery sq
            left join
               max_versions mv on mv.id = sq.id
            where
               sq.version != mv.max_version;
               """
    )

    op.execute(
        """
        with subquery as (
            select
                rpv.id,
                payment_line_item_id,
                refund_amount,
                refund_type,
                disbursement_status_code,
                disbursement_date,
                created_on,
                updated_on,
                created_by,
                created_name,
                updated_by,
                updated_name,
                t.issued_at as changed,
                COALESCE(ROW_NUMBER() OVER (PARTITION BY rpv.id ORDER BY rpv.transaction_id ASC), 1) as version
            from 
               refunds_partial_version rpv
            left join
               transaction t on rpv.transaction_id = t.id
        ),
        max_versions as (
            select
               id,
               max(version) as max_version
            from subquery sq
            group by id
        )
        
        insert into
            refunds_partial_history (id, payment_line_item_id, refund_amount, refund_type, disbursement_status_code,
               disbursement_date, created_on, updated_on, created_by, created_name, updated_by,
               updated_name, changed, version)
        select
            sq.id, payment_line_item_id, refund_amount, refund_type, disbursement_status_code,
               disbursement_date, created_on, updated_on, created_by, created_name, updated_by,
               updated_name, changed, version
        from
            subquery sq
        left join
            max_versions mv on mv.id = sq.id
        where
            sq.version != mv.max_version;
               """
    )


def downgrade():
    op.execute("update refunds_partial set version = 1;")
    op.execute("update payment_accounts set version = 1;")
    op.execute("update eft_short_names set version = 1;")
    op.execute("update distribution_codes set version = 1;")
    op.execute("update cfs_accounts set version = 1;")
    op.execute("update account_fees set version = 1;")
    op.execute("delete from refunds_partial_history;")
    op.execute("delete from payment_accounts_history;")
    op.execute("delete from eft_short_names_history;")
    op.execute("delete from distribution_codes_history;")
    op.execute("delete from cfs_accounts_history;")
    op.execute("delete from account_fees_history;")
