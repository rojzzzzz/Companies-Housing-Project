{{ config(materialized='incremental', incremental_strategy='delete+insert',
          unique_key='observed_date', full_refresh=false) }}

select
    {{ observation_date() }} as observed_date,
    '{{ run_started_at.isoformat() }}'::timestamptz as observed_at,
    {{ company_number('company_number') }} as company_key,
    c.*
from {{ source('staging', 'company') }} c
