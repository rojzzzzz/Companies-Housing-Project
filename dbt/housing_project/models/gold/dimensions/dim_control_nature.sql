select distinct
    nature_of_control as control_nature_key,
    initcap(replace(nature_of_control, '-', ' ')) as control_nature_label,
    case
        when nature_of_control like 'ownership-of-shares-%'
            or nature_of_control like 'ownership-of-surplus-assets-%' then 'Ownership'
        when nature_of_control like 'voting-rights-%' then 'Voting'
        when nature_of_control like 'right-to-appoint-and-remove-directors%'
            or nature_of_control like 'right-to-appoint-and-remove-members%' then 'Appointment rights'
        when nature_of_control like 'significant-influence-or-control%' then 'Significant influence'
        else 'Other'
    end as control_category
from {{ ref('int_psc_control_observation') }}
