-- Everything that does not add up, in one queue with an owner. A break keeps its id across runs, so a
-- person's decision (ops.break_actions) stays with it.
with breaks as (
  select
    'payment_' || status as kind,
    'operations' as owner,
    feeder, null::text as fund, client_key, call_id as reference,
    expected_eur, received_eur as actual_eur, difference_eur,
    case when status = 'overdue' then due_date + {{ var('overdue_grace_days') }} else last_received_on end as opened_on,
    case status
      when 'overdue' then 'No payment for this call after the grace period.'
      when 'short' then 'Paid less than the call.'
      when 'over' then 'Paid more than the call.'
      when 'duplicate' then 'Paid the same call twice: refund one payment.'
    end as detail
  from {{ ref('int_payment_status') }}
  where status in ('overdue', 'short', 'over', 'duplicate')

  union all
  select
    'unmatched_receipt', 'operations', feeder, null, null, receipt_id,
    null, amount, amount, booked_on,
    'Money received that no call and no known client account explains.'
  from {{ ref('int_receipt_matching') }}
  where method = 'unmatched' and not provisional

  union all
  select
    'statement_held', 'fund_accounting', tf.feeder, h.fund, null, 'file ' || h.file_id,
    null, null, null, h.received_on, h.hold_reason
  from {{ ref('statement_holds') }} h
  join {{ ref('stg_target_funds') }} tf using (fund)

  union all
  select
    'statement_late', 'fund_accounting', feeder, fund, null, to_char(quarter_end, 'YYYY-MM-DD'),
    null, null, null, quarter_end + {{ var('statement_due_days') }},
    'No statement for this quarter ' || ({{ as_of() }} - quarter_end) || ' days after quarter end; the NAV is estimated.'
  from {{ ref('int_fund_quarters') }}
  where estimate_reason = 'statement late'

  union all
  -- what the manager says we paid in against what the bank says we paid, per fund
  select
    'gp_cash_mismatch', 'fund_accounting', q.feeder, q.fund, null, to_char(q.quarter_end, 'YYYY-MM-DD'),
    round(q.paid_in_ccy, 2), round(bank.paid_ccy, 2), round(bank.paid_ccy - q.paid_in_ccy, 2), q.quarter_end,
    'Paid-in capital on the statement differs from the calls paid from the feeder account.'
  from {{ ref('int_fund_quarters') }} q
  join lateral (
    select sum(case when tf.currency = 'USD' then -e.amount * {{ usd_per_eur('e.booking_date') }} else -e.amount end) as paid_ccy
    from {{ ref('stg_bank_entries') }} e
    join {{ ref('stg_target_funds') }} tf on tf.fund = e.gp_fund
    where e.entry_kind = 'gp_call' and e.gp_fund = q.fund and e.booking_date <= q.quarter_end
  ) bank on true
  where q.nav_source = 'statement'
    and abs(coalesce(bank.paid_ccy, 0) - q.paid_in_ccy) > greatest(0.005 * q.paid_in_ccy, 1)
),
actions as (
  select distinct on (break_id) break_id, action, note, actor, at
  from {{ source('ops', 'break_actions') }}
  order by break_id, at desc, id desc
)
select
  md5(b.kind || '|' || coalesce(b.feeder, '') || '|' || coalesce(b.fund, '') || '|' || coalesce(b.client_key, '') || '|' || coalesce(b.reference, '')) as break_id,
  b.*,
  greatest({{ as_of() }} - b.opened_on, 0) as age_days,
  case when a.action = 'resolve' then 'resolved' else 'open' end as status,
  a.note as last_note,
  a.actor as last_actor,
  a.at as last_action_at
from breaks b
left join actions a on a.break_id = md5(b.kind || '|' || coalesce(b.feeder, '') || '|' || coalesce(b.fund, '') || '|' || coalesce(b.client_key, '') || '|' || coalesce(b.reference, ''))
