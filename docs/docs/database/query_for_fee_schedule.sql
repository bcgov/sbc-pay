select 
	fs.corp_type_code as corp_type_code,
	fs.filing_type_code as filing_type_code,
	ft.description as filing_type,
	fc.amount as amount,
	p_fc.amount as priority_fee,
	fut_fc.amount as future_effective_fee
from 
	(
		(
			(fee_schedule fs left join fee_code fc on fc.code=fs.fee_code) 
			left join fee_code p_fc on p_fc.code=fs.priority_fee_code)
		left join fee_code fut_fc on fut_fc.code=fs.future_effective_fee_code) 
	left join filing_type ft on ft.code=fs.filing_type_code
order by corp_type_code desc, filing_type_code asc