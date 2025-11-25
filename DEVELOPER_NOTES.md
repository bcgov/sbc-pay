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

EX. Migrations should be done in two steps:
Migrations are structure only
Outside of that we migrate / modify the data

This mitgates the risk of a bad migration.

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

10. Why are there so many routing slip jobs? 

FRCR doesn't allow us to do a PATCH or a PUT on the receipt object. We have to recreate the receipt from scratch for corrections.

11. How do we tell if CAS/CFS are in sync with SBC-PAY? 

Can spot check with invoices and hit the endpoints to compare the values. We're working on something in the future to get a dump of all of CAS/CFS so we can easily compare using that. 

12. Why is there CANCELLED/CREDITED/REFUNDED? 

Because we have no way of executing PAD refunds, we can only credit a CFS account or cancel the transaction before it happens. 

13. How do I get PAD/EJV invoices unstuck out of APPROVED or into their finalized state?

PAD:
We have a few notebooks available - ideally check to see the if the CSV file has processed in the payment reconciliation queue. 

Modify this notebook to look at all invoices, it will query CFS - if the amount_due is > 0, we know it's uncharged or unpaid. 

If amount_due from CFS = 0, it's possible some of the CSV files (take a look at the cas_settlements table) weren't processed. 

https://github.com/bcgov-registries/ops-support/blob/main/support/ops/relationships/datafetch/pad-pending-invoice-query-cas.ipynb

EJV:
We're currently in the process of building a notebook that can assist with this. Basically make sure all of the FEEDBACK files were processed correctly. 
If they weren't or are missing, contact CAS. 

14. How do I execute a partial credit for PAD (we don't do PAD refunds)?

Take a look at this notebook:
https://github.com/bcgov-registries/ops-support/blob/main/support/ops/relationships/datafix/partial-refund-pad.ipynb

15. How can we reconcile payments with CAS/CFS and BCOL? 

It's possible to use CPRD to look at payments in BCOL and match them up to payments in SBC-PAY. 
Example query:

`SELECT * FROM BCONLINE_BILLING_RECORD where key = 'REG01788290';`

For CAS/CFS - we're in the process of building a data warehousing solution so we can query cross database hopefully to line up some results. 

16. How do I generate missing statements?

This query should identify gaps after 2022-01-01:
```
select * from
(
select ('python3 invoke_jobs.py GENERATE_STATEMENTS ' || i::date) as command ,i::date, 'DAILY', (select count(*) from statements s where s.to_date = i::date and frequency = 'DAILY') as statement_count from generate_series('2022-01-01',now() - interval '2 day', '1 day'::interval) i
) t1 where statement_count = 0;
```

EX It will spit out a command, add in the bcrosAccountId or authAccountId:
`python3 invoke_jobs.py GENERATE_STATEMENTS 2022-06-25 <accountId>`

Connect to the job pod, and run this line. 

Note: logs might differ a bit here, bcrosAccountId/authAccountId was recently added.
```
$ python3 invoke_jobs.py GENERATE_STATEMENTS 2022-06-25 <accountId>
----------------------------Scheduler Ran With Argument-- GENERATE_STATEMENTS
2023-03-16 18:37:48,690 - invoke_jobs - INFO in invoke_jobs:invoke_jobs.py:50 - create_app: <<<< Starting Payment Jobs >>>>
2023-03-16 18:37:49,035 - invoke_jobs - DEBUG in statement_task:statement_task.py:47 - generate_statements: Generating statements for: 2022-06-25 using date override.
2023-03-16 18:37:49,094 - invoke_jobs - DEBUG in statement_task:statement_task.py:69 - _generate_daily_statements: Found 25 accounts to generate DAILY statements
2023-03-16 18:37:49,094 - invoke_jobs - DEBUG in statement_task:statement_task.py:117 - _create_statement_records: Statements for day: 2022-06-25
2023-03-16 18:37:49,909 - invoke_jobs - DEBUG in statement_task:statement_task.py:165 - _clean_up_old_statements: Removing 0 existing duplicate/stale statements.
2023-03-16 18:37:52,090 - invoke_jobs - DEBUG in statement_task:statement_task.py:84 - _generate_weekly_statements: Found 12583 accounts to generate WEEKLY statements
2023-03-16 18:37:52,090 - invoke_jobs - DEBUG in statement_task:statement_task.py:121 - _create_statement_records: Statements for week: 2022-06-19 to 2022-06-25
2023-03-16 18:37:58,453 - invoke_jobs - DEBUG in statement_task:statement_task.py:165 - _clean_up_old_statements: Removing 1 existing duplicate/stale statements.
2023-03-16 18:41:54,102 - invoke_jobs - INFO in invoke_jobs:invoke_jobs.py:99 - run: <<<< Completed Generating Statements >>>>
```


17. How to void a routing slip that already has transactions? 

https://github.com/bcgov-registries/ops-support/issues/2535 - Perhaps in the future we'll build this into the job.

18. How to restart CAS EJV inbox files that weren't processed for some reason? 

I'd check the EJV_FILES table, if it's missing some feedback files, search invoice ids through those feedback files by using the download-pay-minio.ipynb in the ops repo. 
If they don't exist in there and it's been a couple of days, you may need to manually rename some of the inbox files to the current date and upload them using oc rsync +
SFTP commands on the ftp-poller pod.


19. How do i deal with a broken index?

Example:
```
self.dialect.do_execute(
File "/usr/local/lib/python3.8/site-packages/sqlalchemy/engine/default.py", line 608, in do_execute
cursor.execute(statement, parameters)
sqlalchemy.exc.InternalError: (psycopg2.errors.IndexCorrupted) index "ix_invoices_payment_account_id" contains unexpected zero page at block 8311
HINT: Please REINDEX it.
```

Log onto the postgres pod - run:

REINDEX (VERBOSE) DATABASE CONCURRENTLY "pay-db";

If you run into duplicate keys, remove them and keep re-running the indexing.

20. How do I replay GCP PUBSUB queue messages?

You should be able to look on the pod and see the message for example:

2024-06-10 20:31:09,969 - account_mailer - INFO in worker:worker.py:49 - worker: Event message received: {"id": "a13c5ed0-a36f-4260-8b46-cff89a0dcd71", "source": "sbc-auth-auth-api", "subject": null, "time": "2024-06-10T20:31:09.745295+00:00", "type": "bc.registry.auth.staffReviewAccount", "data": {"emailAddresses": "xxx@hello.ca", "contextUrl": "
https://gogo.ca//review-account/1127"
, "userFirstName": "REG", "userLastName": "99"}}

1. Add in "specversion": "1.0"
2. Add in "datacontenttype": "application/json"
3. ALSO change the ID (it's saved in a table typically to prevent double messages)

you can build it into a Gcloud message to replay:

gcloud pubsub topics publish projects/<project>/topics/<topic> --message='{"specversion": "1.0", "datacontenttype": "application/json", "id": "c13c5ed0-a36f-4260-8b46-cff89a0dcd71", "source": "sbc-auth-auth-api", "subject": null, "time": "2024-06-10T20:31:09.745295+00:00", "type": "bc.registry.auth.staffReviewAccount", "data": {"emailAddresses": "xxx@hello.ca", "contextUrl": "
https://gogo.ca//review-account/1127"
, "userFirstName": "REG", "userLastName": "99"}}

it will work and process on the pod.


21. Where are the reports generated (report-api)? 
Here: https://github.com/bcgov/bcros-common/

22. How do I resolve some of the database performance issues? Take a look at some of the longer running queries if they're stuck:

SELECT pid, usename, query, state,
       EXTRACT(EPOCH FROM (now() - query_start)) AS duration
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

or 

SELECT *
FROM pg_stat_activity
WHERE state = 'active';

Terminate long running queries if required, for long running query operations, if it is a parallel worker you should kill the leader_pid as well or it can just spawn more parallel workers:

SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid in (146105,
              146355,
              146394
    );

23. How do I use overrides to send EFT statement reminders/due notifications or set overdue on invoices?
    
Provide the override action, date override and auth account id. If there is no accountId, it will be applied environment wide.     
`python3 invoke_jobs.py STATEMENTS_DUE <action> <dateOverride> <accountId>`

Supported Actions:

NOTIFICATION - send payment reminder or due notification based on date override.
e.g. Payment Reminder (date override should be 7 days before the last day)
`python3 invoke_jobs.py STATEMENTS_DUE NOTIFICATION 2024-10-24 1234`

e.g. Payment Due (date override should be on the last day of the month)
`python3 invoke_jobs.py STATEMENTS_DUE NOTIFICATION 2024-10-31 1234`

OVERDUE - set invoices that are overdue to overdue status
e.g. Set overdue status for overdue invoices on auth account 1234.
`python3 invoke_jobs.py STATEMENTS_DUE OVERDUE 2024-10-15 1234`

Date Override: The date you want to emulate the job is running on.
Account Id: The auth account id to run the job against.


24. How do I manually apply an eft payment to a specific statement?

Here: https://drive.google.com/file/d/12WqEis2rQMyKHFNitZRukXWlSLKTa-x1/view?usp=drive_link

25. How do I quickly grab the feedfack files for inspection?

gsutil -m cp -r gs://{bucketName}/* {destinationFolder}

