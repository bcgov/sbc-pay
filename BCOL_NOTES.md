These notes are specific to the operation of BCOL. 

Invoice creation:

PAY-API -> BCOL-API -> BCOL WEB SERVICE (SOAP) - Charge Account or Debit Account methods 

`POST {{pay-api-base-url}}/api/v1/payment-requests`

Note: We don't send along the amount for the transactions fees, we use the appropriate code to bill for the correct service fees.

Refunds:

Refunds are not automated for BCOL. When the refund pay-api endpoint
`POST {{pay-api-base-url}}/api/v1/payment-requests/{invoiceId}/refunds`

is hit a queue event is triggered to the account-mailer in the auth project. It is sent to the emails for the environment variable:
BCOL_REFUND_REQUEST_RECIPIENTS.

Service fees:

Mapping to BCOL service fees:

SBC-PAY calculates the service fee amount and includes it in the bcol_service that calls the BCOL-API. 

It determines by the service fee which BCOL fee code to use:

![image](https://user-images.githubusercontent.com/3484109/233172026-8bfaeeac-ea4f-45fb-842d-8fd918aa879b.png)

These are the general BCOL fee codes we have:

![image](https://user-images.githubusercontent.com/3484109/233171890-cd840bde-c10a-45ea-88c1-0d0e3dd0ba7c.png)

These are the BCOL fees setup in BCONLINE:

![image](https://user-images.githubusercontent.com/3484109/233184831-d8e55393-adfd-48a6-9330-a2ba9194a434.png)

How to test:

It's possible to use CPRD to look at payments in BCOL and match them up to payments in SBC-PAY. Example query:

SELECT * FROM BCONLINE_BILLING_RECORD where key = 'REG01788290';

Outstanding issues:

We have some issues with invoices that seem to disappear (very rarely), not sure if this is an sbc-pay problem or it's BCOL.
We're working on a reconciliation platform to make it easier to compare CPRD (BCONLINE data replica) to SBC-PAY.
