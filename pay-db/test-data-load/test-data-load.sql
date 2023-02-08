do $$
DECLARE v_auth_account_id int := 2062;
DECLARE number_of_invoices int := 100000;
DECLARE v_payment_account_id int;
DECLARE v_cfs_account_id int;
DECLARE v_invoice_id int;
DECLARE v_payment_method_code VARCHAR;
DECLARE v_fee_schedule_id int;
DECLARE v_fee_distribution_id int;
DECLARE random_date timestamp;
DECLARE random_text VARCHAR;
DECLARE random_dollar_amount numeric;
DECLARE performance_random_text VARCHAR;

BEGIN
for i in 0..number_of_invoices loop
	SELECT ('[0:2]={PAD,DRAWDOWN,EJV}'::text[])[trunc(random()*3)] into v_payment_method_code; 
	SELECT fee_schedule_id into v_fee_schedule_id FROM fee_schedules where corp_type_code = 'PPR' ORDER BY RANDOM() LIMIT 1;
	SELECT NOW() + (random() * (interval '90 days')) + '30 days' into random_date;
	SELECT floor(random() * (1000 - 1 + 1) + 1)::numeric into random_dollar_amount;
	SELECT SUBSTRING(md5(random()::text),1,20) into random_text;
	SELECT CONCAT('PERFORMANCE-TEST-', md5(random()::text)) as text into performance_random_text;
	-- raise notice 'v_fee_schedule_id: %, random_date: % random_dollar_amount: %, random_text: %, performance_random_text: %', v_fee_schedule_id, random_date, random_dollar_amount, random_text, performance_random_text;

	INSERT INTO payment_accounts (auth_account_id, name) values (v_auth_account_id, performance_random_text) RETURNING id INTO v_payment_account_id;
	INSERT INTO cfs_accounts (account_id, status) values (v_payment_account_id, 'INACTIVE') RETURNING id INTO v_cfs_account_id;

	INSERT INTO invoices 
			(created_by, created_on, updated_by, updated_on, invoice_status_code, total, paid, payment_date, refund, folio_number, service_fees, business_identifier,
				corp_type_code, created_name, updated_name, dat_number, bcol_account, payment_account_id, cfs_account_id, payment_method_code, disbursement_status_code, details, disbursement_date) 
			values 
			(random_text, random_date, random_text, random_date, 'PAID', random_dollar_amount, random_dollar_amount, 
				random_date, 0, random_text, 0, random_text, 'PPR', random_text, random_text, '', null, v_payment_account_id, v_cfs_account_id, v_payment_method_code, null, json_build_array(json_build_object('key', 'Registration Number:', 'value', random_text)), null) 
			RETURNING id INTO v_invoice_id;
	INSERT INTO invoice_references (invoice_id, invoice_number, status_code) values (v_invoice_id, performance_random_text, 'COMPLETED');
	INSERT INTO payment_line_items (invoice_id, filing_fees, fee_schedule_id, quantity, description, gst, pst, total, line_item_status_code, future_effective_fees, priority_fees, waived_by, waived_fees, fee_distribution_id, service_fees) 
		values 
									(v_invoice_id, random_dollar_amount, v_fee_schedule_id, 1, random_text, 0, 0, random_dollar_amount, 'ACTIVE', 0, 0, null, 0, null, 0);
	if i % 1000 = 0 THEN
		INSERT INTO invoice_references (invoice_id, invoice_number, status_code) values (v_invoice_id, performance_random_text, 'COMPLETED');
	end if;
	if i % 1000 = 0 THEN
		INSERT INTO payment_line_items (invoice_id, filing_fees, fee_schedule_id, quantity, description, gst, pst, total, line_item_status_code, future_effective_fees, priority_fees, waived_by, waived_fees, fee_distribution_id, service_fees) 
		values 
									(v_invoice_id, random_dollar_amount, v_fee_schedule_id, 1, random_text, 0, 0, random_dollar_amount, 'ACTIVE', 0, 0, null, 0, null, 0);
	END IF;
END LOOP;
commit;
end $$;
