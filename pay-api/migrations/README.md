## Migrating Pay-db

Run `python manage.py db migrate`

If you are updating a large table (i.e. invoices, invoice_references, etc.) add `op.execute("set statement_timeout=20000;")` to the top of your new migration scripts for upgrade/downgrade. This will prevent the deployment from causing errors in prod when it takes too long to complete (> 20 seconds).

_Note: If it takes too long this will cause the prehook to fail in the deployment so you will need to watch it and redeploy at a less busy time if necessary_
