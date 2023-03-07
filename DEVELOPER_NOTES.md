1. Why we are using the sync worker and not gevent etc? 

Our queues rely on asyncio, running pay-api under gevent causes issues with queues (asyncio wont play nice and states there is an existing loop).

2. What do the payment_date, refund_dates signify in the invoices table?

These are when the invoice has moved to PAID or CANCELLED/CREDITED/REFUNDED. This isn't the exact date the payment has been executed, it's the date that we have received feedback and confirmed the invoice was finalized. These fields were added in there because we only had the created_on, updated_on fields before.. which can easily be overwritten by disbursement.

3. What should I watch out for while doing migrations?

If you are updating a large table (i.e. invoices, invoice_references, etc.) add `op.execute("set statement_timeout=20000;")` to the top of your new migration scripts for upgrade/downgrade. This will prevent the deployment from causing errors in prod when it takes too long to complete (> 20 seconds).

4. Why are we using two different serialization methods (Marshmallow and Cattrs)?

We're slowly converting to Cattrs from Marshmallow, Cattrs is quite a bit faster and more modern. Marshmallow is fairly slow in performance, I've tried installing some helper packages to increase the performance but it's still fairly slow. Cattrs was used for the serialization of invoices (can be up to 60,000 invoices). 

5. Why is the service fee not included when sending a payload for BC Online?

It's not included because it's set on the BC Online side. 

6. What is disbursement? 

It's the terminology we use to pay our partners. For example there is EJV disbursement for Ministry partners, we have AP Disbursement (EFT) for Non-Ministry Partners. We debit our internal GL (excluding service fees) and credit an external GL or bank account. 
