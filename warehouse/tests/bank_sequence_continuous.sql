-- Statement sequence numbers per account have no gaps: a missing statement would hide bookings.
select feeder, sequence, prev_sequence
from (
  select feeder, sequence, lag(sequence) over (partition by feeder order by sequence) as prev_sequence
  from {{ ref('stg_bank_statements') }}
) s
where prev_sequence is not null and sequence <> prev_sequence + 1
