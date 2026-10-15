-- A PSC identifies an entry in a company's register, not a global person.
with latest_observation as (
    select psc_key, max(observed_date) as observed_date
    from {{ ref('int_psc_observation') }}
    group by psc_key
)

select
    psc.psc_key,
    psc.link_self as source_psc_id,
    psc.name,
    psc.kind,
    psc.nationality,
    psc.country_of_residence,
    psc.legal_form,
    psc.legal_authority,
    psc.country_registered,
    psc.place_registered,
    psc.registration_number,
    psc.observed_date as last_observed_date
from {{ ref('int_psc_observation') }} as psc
join latest_observation as latest
    on psc.psc_key = latest.psc_key
    and psc.observed_date = latest.observed_date
