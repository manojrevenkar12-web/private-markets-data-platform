-- Money in from clients: booked entries from the bank, plus instant notifications not yet on a statement
-- (provisional, shown in today's cash view only).
select
  bank_ref as receipt_id, 'bank' as source, false as provisional, feeder, booking_date as booked_on,
  amount, counterparty_key, remittance, ref_call_id, ref_client_key
from {{ ref('stg_bank_entries') }}
where entry_kind = 'client_receipt'
union all
select
  event_id, 'event', true, feeder, received_on, amount, counterparty_key, remittance, ref_call_id, ref_client_key
from {{ ref('stg_payment_events') }}
where not on_statement
