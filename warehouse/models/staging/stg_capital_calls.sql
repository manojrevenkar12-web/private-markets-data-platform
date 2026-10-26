select call_id, feeder, notice_date, due_date, percent
from {{ source('raw', 'capital_calls') }}
where notice_date <= {{ as_of() }}
