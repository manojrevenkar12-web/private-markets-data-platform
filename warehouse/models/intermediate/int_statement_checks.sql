-- Checks a statement has to pass against the fund's own history before its numbers are used. A statement
-- that fails one is held: the quarter's NAV is estimated until operations release it or a corrected
-- statement arrives. Typical cause: amounts in thousands without the statement saying so.
with v as (
  select
    sv.*,
    tc.commitment as master_commitment,
    tc.commitment is not null and abs(sv.commitment - tc.commitment) > 0.005 * tc.commitment as commitment_mismatch
  from {{ ref('int_statement_versions') }} sv
  left join {{ ref('stg_target_commitments') }} tc using (fund)
),
prev as (
  select
    v.*,
    p.period_end as prev_period_end,
    p.nav as prev_nav,
    p.paid_in as prev_paid_in,
    p.distributed as prev_distributed
  from v
  left join lateral (
    -- the comparison is against the last earlier statement that at least agrees on the commitment
    select * from v p
    where p.fund = v.fund and p.period_end < v.period_end and p.known_from <= v.known_from and not p.commitment_mismatch
    order by p.period_end desc, p.version desc
    limit 1
  ) p on true
),
scored as (
  select
    prev.*,
    prev_nav + (paid_in - prev_paid_in) - (distributed - prev_distributed) as expected_nav
  from prev
),
flagged as (
  select
    scored.*,
    case when prev_nav is null then null
         else round(abs(nav - expected_nav) / greatest(abs(expected_nav), abs(prev_nav), 1), 4) end as unexplained_move,
    prev_paid_in is not null and (paid_in < prev_paid_in * 0.995 or distributed < prev_distributed * 0.995) as cumulative_decrease
  from scored
)
select
  flagged.*,
  coalesce(unexplained_move > {{ var('nav_move_threshold') }}, false) as nav_move_too_large,
  (commitment_mismatch or cumulative_decrease or coalesce(unexplained_move > {{ var('nav_move_threshold') }}, false))
    and not exists (select 1 from {{ source('ops', 'statement_releases') }} r where r.file_id = flagged.file_id) as held,
  concat_ws('; ',
    case when commitment_mismatch then 'commitment differs from the agreed ' || master_commitment end,
    case when cumulative_decrease then 'paid-in or distributions fell against the previous quarter' end,
    case when unexplained_move > {{ var('nav_move_threshold') }} then
      'NAV moved ' || round(unexplained_move * 100) || ' % more than its calls and distributions explain' end
  ) as hold_reason
from flagged
