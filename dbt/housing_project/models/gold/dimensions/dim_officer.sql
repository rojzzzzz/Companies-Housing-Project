-- Source identity is scoped to an appointment. Do not merge people by name.
select {{ gold_key(['link_self']) }} as officer_key,
       link_self as source_appointment_id, person_number::text as person_number,
       name, nationality, country_of_residence, birth_month, birth_year
from {{ source('staging', 'officers') }}
