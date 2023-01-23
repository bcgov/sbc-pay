--BCA MONTHLY: Naming Convention should be BCA_MONTHLY_YYYYMMDD (example: BCA_MONTHLY_20221001)
--(PAY-DB)

SELECT 
	to_char(i.created_on at time zone 'utc' at time zone 'pst','MM-DD-YYYY') AS "DATE(PST)",
	pa.auth_account_id AS "ACCOUNT NUMBER",
	pa.name AS "ACCOUNT NAME",
	pa.bcol_user_id AS "BCOL USER ID",
	i.created_name AS "USER NAME",
	ft.description AS "PRODUCT NAME",
	ft.code AS "PRODUCT CODE",
	i.folio_number as "FOILO NUMBER",
	i.id AS "INVOICE ID",
	i.payment_method_code AS "PAYMENT METHOD",
	i.invoice_status_code AS "INVOICE STATUS",
	(i.total - i.service_fees) AS "PRODUCT AMOUNT (stat fee)",
	pli.gst AS "PRODUCT GST",
	i.service_fees AS "SERVICE FEE AMOUNT",
	pli.gst AS "SERVICE FEE GST",
	i.total AS "TOTAL AMOUNT (stat fee+ service fee)"
FROM 
	(((invoices i
    LEFT JOIN payment_accounts pa ON ((pa.id = i.payment_account_id)))
	LEFT JOIN account_fees af ON af.account_id = pa.id)
	LEFT JOIN invoice_references ir ON ((i.id = ir.invoice_id))
	LEFT JOIN payment_line_items pli ON ((pli.invoice_id = i.id))
	LEFT JOIN fee_schedules fs ON ((pli.fee_schedule_id = fs.fee_schedule_id))
	LEFT JOIN filing_types ft ON ((ft.code = fs.filing_type_code))
	)
where to_char(i.created_on at time zone 'utc' at time zone 'pst','YYYY-MM') = '2022-12'
and i.corp_type_code = 'BCA'
order by 1;
