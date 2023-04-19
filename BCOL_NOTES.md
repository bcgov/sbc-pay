These notes are specific to the operation of BCOL. 

# Invoice creation:

  PAY-API -> BCOL-API -> BCOL WEB SERVICE (SOAP) - Charge Account or Debit Account methods 

  `POST {{pay-api-base-url}}/api/v1/payment-requests`

  Note: We don't send along the amount for the service fees to the BCOL WEB SERVICE, we use the appropriate code to bill for the correct service fees.

# Refunds:

  Refunds are not automated for BCOL. When the refund pay-api endpoint
  `POST {{pay-api-base-url}}/api/v1/payment-requests/{invoiceId}/refunds`

  is hit a queue event is triggered to the account-mailer in the auth project. It is sent to the emails for the environment variable:
  BCOL_REFUND_REQUEST_RECIPIENTS.

# Service fees:

  Mapping to BCOL service fees:

  SBC-PAY calculates the service fee amount and includes it in the bcol_service that calls the BCOL-API. 

  It determines by the service fee which BCOL fee code to use:

  $1.50 or $1.05 -> `bcol_code_full_service_fee`
  $1             -> `bcol_code_partial_service_fee`
  $0             -> `bcol_code_no_service_fee`

  ![image](https://user-images.githubusercontent.com/3484109/233172026-8bfaeeac-ea4f-45fb-842d-8fd918aa879b.png)

  These are the general BCOL fee codes we have:

  ![image](https://user-images.githubusercontent.com/3484109/233171890-cd840bde-c10a-45ea-88c1-0d0e3dd0ba7c.png)

  These are the BCOL fees setup in BCONLINE:

  ![image](https://user-images.githubusercontent.com/3484109/233184831-d8e55393-adfd-48a6-9330-a2ba9194a434.png)

# How to test:

  It's possible to use CPRD to look at payments in BCOL and match them up to payments in SBC-PAY. Example query:

  SELECT * FROM BCONLINE_BILLING_RECORD where key = 'REG01788290';


  BCOL for CSO: 

  CSO has a unique implementation as they use a service account to recharge for partial refunds. 

  ![image](https://user-images.githubusercontent.com/3484109/233185592-fa4534e5-a91f-4bc1-87a2-9f1363a34af1.png)

  They use a service account, which causes the STAFF BCOL to be used typically, but we've overridden this in the segment above.

# Outstanding issues:

  We have some issues with invoices that seem to disappear (very rarely), not sure if this is an sbc-pay problem or it's BCOL.
  We're working on a reconciliation platform to make it easier to compare CPRD (BCONLINE data replica) to SBC-PAY.
