{# Every model lands in the run's build schema; no schema suffixes. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {{ target.schema }}
{%- endmacro %}
