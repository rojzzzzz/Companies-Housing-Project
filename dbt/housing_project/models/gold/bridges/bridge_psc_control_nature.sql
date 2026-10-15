-- One right per PSC observation. A PSC can have several rights.
select
    {{ gold_key(['psc_id', 'observed_date::text']) }} as psc_relationship_key,
    nature_of_control as control_nature_key
from {{ ref('int_psc_control_observation') }}
