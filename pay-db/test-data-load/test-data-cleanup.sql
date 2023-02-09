--# Cleanup if needed
do $$
DECLARE v_auth_account_id varchar := '2062';
BEGIN
DELETE FROM payment_line_items where invoice_id in (SELECT i.id from invoices i join payment_accounts pa on pa.id = i.payment_account_id where auth_account_id = v_auth_account_id);
DELETE FROM invoice_references where invoice_id in (SELECT i.id from invoices i join payment_accounts pa on pa.id = i.payment_account_id where auth_account_id = v_auth_account_id);
DELETE FROM invoices where payment_account_id in (select id from payment_accounts where auth_account_id = v_auth_account_id);
DELETE FROM cfs_accounts where account_id in (SELECT id from payment_accounts where auth_account_id = v_auth_account_id);
DELETE FROM payment_accounts where name like '%PERFORMANCE-TEST%';
end $$;