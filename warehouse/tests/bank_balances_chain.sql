-- Each statement opens where the previous one closed.
select feeder, statement_date, opening, prev_closing
from (
  select feeder, statement_date, opening, lag(closing) over (partition by feeder order by sequence) as prev_closing
  from {{ ref('stg_bank_statements') }}
) s
where prev_closing is not null and opening <> prev_closing
