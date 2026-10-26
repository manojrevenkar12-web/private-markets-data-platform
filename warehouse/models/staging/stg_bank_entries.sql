-- Booked entries on the feeders' accounts. GP calls and distributions are recognised by their remittance.
select
  e.bank_ref,
  e.file_id,
  f.feeder,
  e.booking_date,
  e.amount,
  e.counterparty_key,
  e.remittance,
  e.ref_call_id,
  e.ref_client_key,
  case
    when e.remittance ~ '^Capital call [A-Z0-9]{3,6} ' then 'gp_call'
    when e.remittance ~ '^Distribution [A-Z0-9]{3,6} ' then 'gp_distribution'
    when e.amount < 0 then 'client_distribution'
    else 'client_receipt'
  end as entry_kind,
  substring(e.remittance from '^(?:Capital call|Distribution) ([A-Z0-9]{3,6}) ') as gp_fund
from {{ source('raw', 'bank_entries') }} e
join {{ ref('stg_feeders') }} f on f.collection_account = e.account_iban
where e.booking_date <= {{ as_of() }}
