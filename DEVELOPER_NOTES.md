1. Why we are using the sync worker and not gevent etc? 

Our queues rely on asyncio, running pay-api under gevent causes issues with queues (asyncio wont play nice and states there is an existing loop).

2. What do the payment_date, refund_dates signify in the invoices table?

These are when the invoice has moved to PAID or CANCELLED/CREDITED/REFUNDED. This isn't the exact date the payment has been executed, it's the date that we have received feedback and confirmed the invoice was finalized. These fields were added in there because we only had the created_on, updated_on fields before.. which can easily be overwritten by disbursement.

3. What should I watch out for while doing migrations?

If you are updating a large table (i.e. invoices, invoice_references, etc.) add `op.execute("set statement_timeout=20000;")` to the top of your new migration scripts for upgrade/downgrade. This will prevent the deployment from causing errors in prod when it takes too long to complete (> 20 seconds). If this fails, it's possible to retry.

If this doesn't work, it might be necessary to manually execute the migration.

For example - this kills the database connections, while it executes a manual migration:

```
UPDATE pg_database SET datallowconn = 'false' WHERE datname = 'pay-db';
SELECT pg_terminate_backend(pid)FROM pg_stat_activity WHERE datname = 'pay-db' and application_name <> 'psql'
ALTER TABLE invoices ADD COLUMN disbursement_date TIMESTAMP;
update alembic_version set version_num = '286acad5d366';
UPDATE pg_database SET datallowconn = 'true' WHERE datname = 'pay-db'
```

4. Why are we using two different serialization methods (Marshmallow and Cattrs)?

We're slowly converting to Cattrs from Marshmallow, Cattrs is quite a bit faster and more modern. Marshmallow is fairly slow in performance, I've tried installing some helper packages to increase the performance but it's still fairly slow. Cattrs was used for the serialization of invoices (can be up to 60,000 invoices). 

5. Why is the service fee not included when sending a payload for BC Online?

It's not included because it's set on the BC Online side. It's also possible to check this in CPRD. 

6. What is disbursement? 

It's the terminology we use to pay our partners. For example there is EJV disbursement for Ministry partners, we have AP Disbursement (EFT) for Non-Ministry Partners. We debit our internal GL (excluding service fees) and credit an external GL or bank account. 

7. How is the PAY-API spec updated?

Right now it's a manual process.

8. Where is the payment flow documentation? 

There are bits of it everywhere right now, but Louise is building out all of the documentation - will be uploaded to github shortly.

https://github.com/bcgov/sbc-pay/blob/main/docs/docs/architecture/FAS_Intgeration.md
https://github.com/bcgov-registries/documents/blob/main/pay/EJV.md
https://github.com/bcgov-registries/documents/blob/main/pay/PAD.md

Are great starting points.

9. How do I identify stale invoices that aren't being processed (stuck in APPROVED)?

Via query:

pay-db=# select count(*), payment_method_code from invoices where created_on < now() - interval '20' day and invoice_status_code = 'APPROVED' group by payment_method_code;
 count | payment_method_code
-------+---------------------
  1015 | EJV
     1 | INTERNAL
   665 | PAD
(3 rows)




