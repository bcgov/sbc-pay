-- Seed non_gov_disbursement_config for non-government partners paid via AP/EFT through CGI.
-- Run once per environment after migration d4e5f6a7b8c9.
-- Replace placeholders with the correct CAS supplier credentials for each environment.

INSERT INTO non_gov_disbursement_config (corp_type_code, cas_supplier_number, cas_supplier_site, created_by)
VALUES ('BCA', '$BCA_CAS_SUPPLIER_NUMBER', '$BCA_CAS_SUPPLIER_SITE', 'migration')
ON CONFLICT (corp_type_code) DO NOTHING;
