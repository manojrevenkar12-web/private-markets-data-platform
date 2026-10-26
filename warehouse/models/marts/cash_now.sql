-- Open capital calls today: what is due, what the bank has booked, and what instant notifications say has
-- arrived since the last statement.
select
  e.call_id,
  e.feeder,
  min(e.notice_date) as notice_date,
  min(e.due_date) as due_date,
  count(*) as clients,
  sum(e.expected_eur) as expected_eur,
  sum(s.received_eur) as booked_eur,
  sum(s.provisional_eur) as arrived_since_statement_eur,
  sum(e.expected_eur) - sum(s.received_eur) - sum(s.provisional_eur) as outstanding_eur,
  count(*) filter (where s.received_eur = 0 and s.provisional_eur = 0) as clients_not_paid,
  (select max(received_at) from {{ ref('stg_payment_events') }} pe where pe.feeder = e.feeder) as last_event_at,
  (select max(statement_date) from {{ ref('stg_bank_statements') }} b where b.feeder = e.feeder) as last_statement_on
from {{ ref('int_expected_payments') }} e
join {{ ref('int_payment_status') }} s using (expected_id)
where e.due_date + {{ var('overdue_grace_days') }} >= {{ as_of() }}
group by e.call_id, e.feeder
