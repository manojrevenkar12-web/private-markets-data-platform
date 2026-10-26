select s.file_id, f.feeder, s.statement_date, s.sequence, s.opening, s.closing
from {{ source('raw', 'bank_statements') }} s
join {{ ref('stg_feeders') }} f on f.collection_account = s.account_iban
where s.statement_date <= {{ as_of() }}
