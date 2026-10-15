select 'capital_row_loss', 'all'
where (select count(*) from {{ ref('fct_capital_declaration') }})
   <> (select count(*) from {{ source('staging', 'capital') }})
