from admin.views.fee_code import FeeCodeConfig, FeeCode


def test_fee_codee_columns(db):
    view = FeeCodeConfig(FeeCode, db.session, allowed_role='admin_view')
    columns = view.get_list_columns()

    for col in columns:
        assert col[0] in ('code', 'amount')
