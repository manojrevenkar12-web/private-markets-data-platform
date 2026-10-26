-- Instant notifications. An event whose payment is already on a bank statement is not counted twice.
select
  e.event_id,
  f.feeder,
  e.amount,
  e.counterparty_key,
  e.remittance,
  e.ref_call_id,
  e.ref_client_key,
  e.received_at,
  (e.received_at at time zone 'Europe/Berlin')::date as received_on,
  e.bank_ref,
  exists (select 1 from {{ source('raw', 'bank_entries') }} b where b.bank_ref = e.bank_ref) as on_statement
from {{ source('raw', 'payment_events') }} e
join {{ ref('stg_feeders') }} f on f.collection_account = e.account_iban
where (e.received_at at time zone 'Europe/Berlin')::date <= {{ as_of() }}
