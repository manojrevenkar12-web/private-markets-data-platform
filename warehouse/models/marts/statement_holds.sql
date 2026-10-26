-- Statements that read correctly but disagree with the fund's history, and why. Their quarter is estimated.
select c.file_id, c.fund, tf.fund_name, c.period_end, c.version, c.received_on, c.hold_reason,
       c.nav, c.prev_nav, c.unexplained_move, c.currency, c.file_path
from {{ ref('int_statement_checks') }} c
join {{ ref('stg_target_funds') }} tf using (fund)
where c.held
