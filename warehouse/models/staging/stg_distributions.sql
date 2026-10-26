select distribution_id, feeder, pay_date, percent
from {{ source('raw', 'distributions') }}
where pay_date <= {{ as_of() }}
