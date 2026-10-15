{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='observed_date',
    full_refresh=false
) }}

-- Keep one observation per PSC per day. A rerun replaces that day's rows.
select
    {{ observation_date() }} as observed_date,
    '{{ run_started_at.isoformat() }}'::timestamptz as observed_at,
    {{ company_number('company_number') }} as company_key,
    {{ gold_key(['link_self']) }} as psc_key,
    psc.*
from {{ source('staging', 'psc') }} as psc
