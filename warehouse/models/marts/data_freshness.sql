-- Is every source up to date? One row per source and feed.
-- GP statements: due {{ var("statement_due_days") }} days after each quarter end.
-- Bank: a payment notified by the instant feed must be on a statement within two business days.
-- Payment events: during an open capital call, money arrives daily; a silent feed is suspicious.
with gp (source, feed, label, latest, last_received_on, due) as (
  select
    'gp_statement' as source, tf.fund as feed, tf.fund_name as label,
    max(s.period_end) as latest, max(s.received_on) as last_received_on,
    (date_trunc('quarter', {{ as_of() }} - interval '{{ var("statement_due_days") }} days') - interval '1 day')::date as due
  from {{ ref('stg_target_funds') }} tf
  left join {{ ref('stg_statements') }} s using (fund)
  group by tf.fund, tf.fund_name
),
bank (source, feed, label, latest, last_received_on, due) as (
  select
    'bank_statement', f.feeder, f.feeder_name,
    max(b.statement_date), max(b.statement_date),
    (select min(e.received_on) from {{ ref('stg_payment_events') }} e where e.feeder = f.feeder and not e.on_statement)
  from {{ ref('stg_feeders') }} f
  left join {{ ref('stg_bank_statements') }} b using (feeder)
  group by f.feeder, f.feeder_name
),
events (source, feed, label, latest, last_received_on, due) as (
  select
    'payment_events', f.feeder, f.feeder_name,
    max(e.received_on), max(e.received_on),
    case when exists (select 1 from {{ ref('stg_capital_calls') }} c where c.feeder = f.feeder
                      and {{ as_of() }} between c.notice_date and c.due_date + {{ var('overdue_grace_days') }})
         then ({{ as_of() }} - interval '1 day')::date end
  from {{ ref('stg_feeders') }} f
  left join {{ ref('stg_payment_events') }} e using (feeder)
  group by f.feeder, f.feeder_name
)
select
  source, feed, label, latest, last_received_on, due,
  case when latest is null then 'missing' when latest >= due then 'fresh' else 'late' end as status
from gp
union all
select source, feed, label, latest, last_received_on, due,
  case when due is not null and due < {{ as_of() }} - 3 then 'late' else 'fresh' end
from bank
union all
select source, feed, label, latest, last_received_on, due,
  case when due is null or latest >= due then 'fresh' else 'late' end
from events
