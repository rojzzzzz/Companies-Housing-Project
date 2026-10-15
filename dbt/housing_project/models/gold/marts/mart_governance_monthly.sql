with directors as (
    select *
    from {{ ref('fct_officer_appointment') }}
    where officer_role_key in ('director', 'corporate-director', 'nominee-director')
),

appointment_status as (
    select
        months.company_key,
        months.month_start,
        case
            when directors.appointed_on < months.month_start
                and (directors.resigned_on is null or directors.resigned_on >= months.month_start)
            then 1 else 0
        end as active_at_start,
        case
            when directors.appointed_on <= months.period_end
                and (directors.resigned_on is null or directors.resigned_on > months.period_end)
            then 1 else 0
        end as active_at_end,
        case
            when directors.appointed_on between months.month_start and months.period_end
            then 1 else 0
        end as appointed_this_month,
        case
            when directors.resigned_on between months.month_start and months.period_end
            then 1 else 0
        end as resigned_this_month,
        months.period_end - directors.appointed_on as tenure_days
    from {{ ref('int_company_months') }} as months
    left join directors
        on months.company_key = directors.company_key
),

monthly_totals as (
    select
        company_key,
        month_start,
        sum(active_at_start) as directors_at_start,
        sum(active_at_end) as active_directors,
        sum(appointed_this_month) as appointments,
        sum(resigned_this_month) as resignations,
        avg(case when active_at_end = 1 then tenure_days end) as average_active_tenure_days
    from appointment_status
    group by company_key, month_start
)

select
    {{ gold_key(['totals.company_key', 'totals.month_start::text']) }} as governance_month_key,
    totals.company_key,
    months.company_name,
    totals.month_start,
    months.period_end,
    months.is_partial_month,
    to_char(totals.month_start, 'YYYYMMDD')::integer as month_date_key,
    totals.directors_at_start,
    totals.active_directors,
    totals.appointments,
    totals.resignations,
    totals.appointments - totals.resignations as net_director_change,
    totals.average_active_tenure_days
from monthly_totals as totals
join {{ ref('int_company_months') }} as months
    on totals.company_key = months.company_key
    and totals.month_start = months.month_start
