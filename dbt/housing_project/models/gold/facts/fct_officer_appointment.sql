select {{ gold_key(['link_self']) }} as appointment_key,
       {{ company_number('company_number') }} as company_key,
       {{ gold_key(['link_self']) }} as officer_key,
       officer_role as officer_role_key, link_self as source_appointment_id,
       appointed_on::date as appointed_on, resigned_on::date as resigned_on,
       to_char(appointed_on, 'YYYYMMDD')::integer as appointed_date_key,
       to_char(resigned_on, 'YYYYMMDD')::integer as resigned_date_key,
       {{ observation_date() }} as observed_date,
       appointed_on <= {{ observation_date() }}
           and (resigned_on is null or resigned_on > {{ observation_date() }}) as is_active,
       least(coalesce(resigned_on, {{ observation_date() }}), {{ observation_date() }}) - appointed_on as tenure_days
from {{ source('staging', 'officers') }}
