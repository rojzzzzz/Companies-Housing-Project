select 'invalid_appointment_period', appointment_key
from {{ ref('fct_officer_appointment') }}
where resigned_on < appointed_on
