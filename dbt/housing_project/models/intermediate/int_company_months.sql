-- One row per company and month, including months with no activity.
select
    company.company_key,
    company.company_name,
    calendar.month_start,
    least(calendar.month_end, {{ observation_date() }}) as period_end,
    calendar.month_end > {{ observation_date() }} as is_partial_month
from {{ ref('dim_company') }} as company
join {{ ref('dim_date') }} as calendar
    on calendar.date_day = calendar.month_start
    and calendar.month_start >= date_trunc('month', company.date_of_creation)
    and calendar.month_start <= {{ observation_date() }}
