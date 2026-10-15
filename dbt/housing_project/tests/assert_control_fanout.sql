select 'control_fanout', 'all'
where (select count(*) from {{ ref('mart_company_control') }})
   <> (select count(*) from {{ ref('fct_company_psc_relationship') }})
