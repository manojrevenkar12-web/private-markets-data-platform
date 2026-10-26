-- Every statement version per fund and quarter, with when it was known: a restatement does not overwrite the
-- quarter, it supersedes the earlier version from the day it arrived (known_from / known_until).
select
  s.*,
  row_number() over w as version,
  count(*) over (partition by fund, period_end) as versions,
  lag(nav) over w as previous_version_nav,
  received_on as known_from,
  lead(received_on) over w as known_until
from {{ ref('stg_statements') }} s
window w as (partition by fund, period_end order by received_on, file_id)
