with control_summary as (
    select
        bridge.psc_relationship_key,
        string_agg(nature.control_nature_key, '; ' order by nature.control_nature_key) as control_natures,
        string_agg(
            case when nature.control_nature_key like 'ownership-of-shares-%'
                then nature.control_nature_key end,
            '; ' order by nature.control_nature_key
        ) as share_ownership_bands,
        string_agg(
            case when nature.control_nature_key like 'voting-rights-%'
                then nature.control_nature_key end,
            '; ' order by nature.control_nature_key
        ) as voting_rights_bands,
        max(
            case when nature.control_nature_key like 'right-to-appoint-and-remove-directors%'
                then 1 else 0 end
        ) = 1 as can_appoint_remove_directors
    from {{ ref('bridge_psc_control_nature') }} as bridge
    join {{ ref('dim_control_nature') }} as nature
        on bridge.control_nature_key = nature.control_nature_key
    group by bridge.psc_relationship_key
)

select
    relationship.*,
    company.company_name,
    controls.control_natures,
    controls.share_ownership_bands,
    controls.voting_rights_bands,
    controls.can_appoint_remove_directors,
    relationship.observed_date = (
        select max(observed_date) from {{ ref('int_psc_observation') }}
    ) as is_latest_observation
from {{ ref('fct_company_psc_relationship') }} as relationship
join {{ ref('dim_company') }} as company
    on relationship.company_key = company.company_key
left join control_summary as controls
    on relationship.psc_relationship_key = controls.psc_relationship_key
