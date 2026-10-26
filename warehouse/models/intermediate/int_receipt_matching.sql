-- Each receipt to the capital call it pays.
-- 1. By reference: call and client named in the remittance, and the payer's account is not someone else's.
-- 2. By account: the payer's account belongs to a client with an open call on this feeder; the call whose
--    amount matches comes first, then the most recent one.
-- 3. Otherwise unmatched: money nobody can place yet.
with r as (
  select r.*, ca.client_key as account_client
  from {{ ref('int_receipts') }} r
  left join {{ ref('stg_client_accounts') }} ca using (counterparty_key)
),
by_reference as (
  select r.receipt_id, e.expected_id, e.client_key, 'reference' as method
  from r
  join {{ ref('int_expected_payments') }} e
    on e.call_id = r.ref_call_id and e.client_key = r.ref_client_key and e.feeder = r.feeder
  where r.account_client is null or r.account_client = r.ref_client_key
),
by_account as (
  select receipt_id, expected_id, client_key, 'account' as method
  from (
    select
      r.receipt_id, e.expected_id, e.client_key,
      row_number() over (
        partition by r.receipt_id
        order by (abs(e.expected_eur - r.amount) <= {{ var('amount_tolerance') }}) desc, e.notice_date desc
      ) as rn
    from r
    join {{ ref('int_expected_payments') }} e
      on e.client_key = r.account_client and e.feeder = r.feeder and e.notice_date <= r.booked_on
    where r.receipt_id not in (select receipt_id from by_reference)
  ) x
  where rn = 1
)
select
  r.receipt_id, r.source, r.provisional, r.feeder, r.booked_on, r.amount, r.counterparty_key,
  coalesce(m.client_key, r.account_client) as client_key,
  m.expected_id,
  coalesce(m.method, 'unmatched') as method
from r
left join (select * from by_reference union all select * from by_account) m using (receipt_id)
