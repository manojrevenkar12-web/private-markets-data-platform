-- One row per statement file that passed its contract. A fund and quarter can have several (restatements).
select
  s.file_id,
  s.fund,
  s.period_end,
  s.currency,
  s.commitment,
  s.paid_in,
  s.distributed,
  s.nav,
  s.unfunded,
  s.statement_date,
  s.unit_scale,
  s.received_on,
  s.parser,
  f.path as file_path
from {{ source('raw', 'gp_statements') }} s
join {{ source('ops', 'files') }} f using (file_id)
where s.received_on <= {{ as_of() }}
