select distinct
    officer_role as officer_role_key,
    initcap(replace(officer_role, '-', ' ')) as role_label
from {{ source('staging', 'officers') }}
