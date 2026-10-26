{% test dbt_utils_unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*)
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

{% test in_range(model, column_name, low, high) %}
select * from {{ model }} where {{ column_name }} < {{ low }} or {{ column_name }} > {{ high }}
{% endtest %}
