1. Why we are using the sync worker and not gevent etc? 

Our queues rely on asyncio, running pay-api under gevent causes issues with queues (asyncio wont play nice and states there is an existing loop)

2. What do the payment_date, refund_dates signify in the invoices table?

These are when the invoice has moved to PAID or CANCELLED/CREDITED/REFUNDED. This isn't the exact date the payment has been executed, it's the date that we have received feedback and confirmed the invoice was finalized. These fields were added in there because we only had the created_on, updated_on fields before.. which can easily be overritten by disbursement.

3. What should I watch out for while doing migrations?

If you are updating a large table (i.e. invoices, invoice_references, etc.) add `op.execute("set statement_timeout=20000;")` to the top of your new migration scripts for upgrade/downgrade. This will prevent the deployment from causing errors in prod when it takes too long to complete (> 20 seconds).
