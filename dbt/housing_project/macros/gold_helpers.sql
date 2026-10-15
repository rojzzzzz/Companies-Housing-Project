{# Shared helpers only: identifier formatting, stable keys and the observation date. #}
{% macro company_number(expression) -%}
case when trim({{ expression }}::text) ~ '^[0-9]+$'
     then lpad(trim({{ expression }}::text), greatest(8, length(trim({{ expression }}::text))), '0')
     else upper(trim({{ expression }}::text)) end
{%- endmacro %}

{% macro gold_key(expressions) -%}
md5(jsonb_build_array({{ expressions | join(', ') }})::text)
{%- endmacro %}

{% macro observation_date() -%}
'{{ var("observation_date", run_started_at.astimezone(modules.pytz.timezone("America/Managua")).strftime("%Y-%m-%d")) }}'::date
{%- endmacro %}

{% test unique_grain(model, columns) %}
select {{ columns | join(', ') }}, count(*)
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
