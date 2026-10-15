{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='observed_date',
    full_refresh=false
) }}

-- Store each right as its own row, rather than packing rights into a string.
select
    psc.observed_date,
    psc.link_self as psc_id,
    rights.nature_of_control
from {{ ref('int_psc_observation') }} as psc
join {{ source('staging', 'psc_nature') }} as rights
    on psc.link_self = rights.psc_id
where psc.observed_date = {{ observation_date() }}
