--BCA MONTHLY: Naming Convention should be BCA_MONTHLY_YYYYMMDD (example: BCA_MONTHLY_20221001)

--(PAY-DB)

SELECT 
	to_char(i.updated_on,'MM-DD-YYYY') AS "DATE",
	af.account_id AS "CUSTOMER ACCOUNT",
	pa.name AS "ACCOUNT NAME",
	pa.bcol_user_id AS "USER ID",
	i.created_name AS "USER NAME",
	af.product AS "PRODUCT TYPE", --REMOVE IT LATER
	ft.description AS "PRODUCT NAME",
	ft.code AS "FEE CODE",
--	null as "TRANSACTION REMARKS", // SIDD can you please check where does this transaction remarks sit
	i.folio_number AS "FOLIO",
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
--	CROSS JOIN jsonb_array_elements(case jsonb_typeof(details) when 'array' then details else '[]' end) AS elem
    LEFT JOIN payment_accounts pa ON ((pa.id = i.payment_account_id)))
	LEFT JOIN account_fees af ON af.account_id = pa.id)
	LEFT JOIN invoice_references ir ON ((i.id = ir.invoice_id))
	LEFT JOIN payment_line_items pli ON ((pli.invoice_id = i.id))
	LEFT JOIN fee_schedules fs ON ((pli.fee_schedule_id = fs.fee_schedule_id))
	LEFT JOIN filing_types ft ON ((ft.code = fs.filing_type_code))
	)
	
where
to_char(i.created_on,'YYYY-MM') = '2022-12' ---change to month you need data for
--and ft.description IN ('Assessment Roll Report','Owner Location Report','Assessment Inventory Report') 
--OR
and ft.code IN ('OLAARTAQ','OLAARTOQ','OLAARTIQ') --BCA has only these 3 fee codes
--and af.product = 'BCA'
order by 1;