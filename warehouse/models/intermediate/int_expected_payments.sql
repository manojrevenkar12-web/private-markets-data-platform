-- What every client owes for every capital call: their commitment times the call's percentage.
select
  c.call_id || ':' || cm.client_key as expected_id,
  c.call_id,
  c.feeder,
  cm.client_key,
  c.notice_date,
  c.due_date,
  c.percent,
  round(cm.amount * c.percent / 100, 2) as expected_eur
from {{ ref('stg_capital_calls') }} c
join (
  select client_key, feeder, sum(amount) as amount, min(signed_on) as signed_on
  from {{ ref('stg_commitments') }}
  group by client_key, feeder
) cm on cm.feeder = c.feeder and cm.signed_on <= c.notice_date
