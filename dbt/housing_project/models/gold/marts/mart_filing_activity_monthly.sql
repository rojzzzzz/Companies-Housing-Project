with categories as (
    select distinct category
    from {{ ref('dim_filing_type') }}
),

company_month_categories as (
    select months.*, categories.category
    from {{ ref('int_company_months') }} as months
    cross join categories
),

filing_counts as (
    select
        filing.company_key,
        date_trunc('month', filing.filed_on)::date as month_start,
        filing_type.category,
        count(*) as filing_count,
        max(filing.filed_on) as last_filed_on
    from {{ ref('fct_filing') }} as filing
    join {{ ref('dim_filing_type') }} as filing_type
        on filing.filing_type_key = filing_type.filing_type_key
    where filing.filed_on <= {{ observation_date() }}
    group by filing.company_key, date_trunc('month', filing.filed_on)::date, filing_type.category
),

monthly_activity as (
    select
        months.company_key,
        months.company_name,
        months.month_start,
        months.category,
        months.is_partial_month,
        coalesce(counts.filing_count, 0) as filing_count,
        counts.last_filed_on
    from company_month_categories as months
    left join filing_counts as counts
        on months.company_key = counts.company_key
        and months.month_start = counts.month_start
        and months.category = counts.category
),

previous_month as (
    select
        *,
        lag(filing_count) over (
            partition by company_key, category
            order by month_start
        ) as previous_month_filing_count
    from monthly_activity
)

select
    {{ gold_key(['company_key', 'month_start::text', 'category']) }} as filing_activity_key,
    *,
    to_char(month_start, 'YYYYMMDD')::integer as month_date_key,
    filing_count - previous_month_filing_count as month_over_month_change,
    100.0 * (filing_count - previous_month_filing_count)
        / nullif(previous_month_filing_count, 0) as month_over_month_change_pct
from previous_month
