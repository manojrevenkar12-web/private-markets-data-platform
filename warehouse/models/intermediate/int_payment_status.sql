-- Where every client stands on every call: paid, paid late, short, over, paid twice, overdue or still open.
with booked as (
  select
    expected_id,
    sum(amount) filter (where not provisional) as received_eur,
    count(*) filter (where not provisional) as receipts,
    min(booked_on) filter (where not provisional) as first_received_on,
    max(booked_on) filter (where not provisional) as last_received_on,
    sum(amount) filter (where provisional) as provisional_eur,
    -- the same amount twice within the window: a duplicate to send back
    max(booked_on) filter (where not provisional) - min(booked_on) filter (where not provisional)
      <= {{ var('duplicate_window_days') }}
      and count(*) filter (where not provisional) >= 2
      and count(distinct amount) filter (where not provisional) = 1 as looks_duplicate
  from {{ ref('int_receipt_matching') }}
  where expected_id is not null
  group by expected_id
)
select
  e.*,
  coalesce(b.received_eur, 0) as received_eur,
  coalesce(b.provisional_eur, 0) as provisional_eur,
  coalesce(b.receipts, 0) as receipts,
  b.first_received_on,
  b.last_received_on,
  coalesce(b.received_eur, 0) - e.expected_eur as difference_eur,
  case
    when coalesce(b.received_eur, 0) = 0 and {{ as_of() }} > e.due_date + {{ var('overdue_grace_days') }} then 'overdue'
    when coalesce(b.received_eur, 0) = 0 then 'open'
    when coalesce(b.looks_duplicate, false) and abs(b.received_eur - 2 * e.expected_eur) <= {{ var('amount_tolerance') }} then 'duplicate'
    when abs(b.received_eur - e.expected_eur) <= {{ var('amount_tolerance') }}
      then case when b.last_received_on > e.due_date + {{ var('overdue_grace_days') }} then 'paid_late' else 'paid' end
    when b.received_eur < e.expected_eur
      then case when {{ as_of() }} > e.due_date + {{ var('overdue_grace_days') }} then 'short' else 'part_paid' end
    else 'over'
  end as status
from {{ ref('int_expected_payments') }} e
left join booked b using (expected_id)
