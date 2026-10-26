-- No receipt is counted against two calls.
select receipt_id, count(*) from {{ ref('int_receipt_matching') }} group by receipt_id having count(*) > 1
