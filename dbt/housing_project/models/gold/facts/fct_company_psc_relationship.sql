with control_counts as (
    select
        psc_id,
        observed_date,
        count(*) as control_count
    from {{ ref('int_psc_control_observation') }}
    group by psc_id, observed_date
)

select
    {{ gold_key(['psc.link_self', 'psc.observed_date::text']) }} as psc_relationship_key,
    psc.company_key,
    psc.psc_key,
    psc.observed_date,
    psc.observed_at,
    to_char(psc.observed_date, 'YYYYMMDD')::integer as observed_date_key,
    to_char(psc.notified_on, 'YYYYMMDD')::integer as notified_date_key,
    to_char(psc.ceased_on, 'YYYYMMDD')::integer as ceased_date_key,
    psc.notified_on,
    psc.ceased_on,
    psc.ceased as source_ceased_flag,
    case
        when psc.ceased = true or psc.ceased_on <= psc.observed_date then false
        when psc.ceased = false and psc.notified_on <= psc.observed_date then true
        else null
    end as is_active,
    psc.name as psc_name_at_observation,
    psc.kind as psc_kind_at_observation,
    coalesce(controls.control_count, 0) > 0 as has_control_details
from {{ ref('int_psc_observation') }} as psc
left join control_counts as controls
    on psc.link_self = controls.psc_id
    and psc.observed_date = controls.observed_date
