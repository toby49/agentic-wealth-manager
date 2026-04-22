with prices as (
    select * from {{ ref('stg_stock_prices') }}
)

, fundamentals as (
    select * from {{ ref('stg_stock_fundamentals') }}
)

select 
    p.ticker as ticker
    , p.date as date
    , p.adj_close as adj_close
    , f.revenue_growth_yoy as revenue_growth_yoy
    , f.operating_margin as operating_margin
    , f.return_on_equity as return_on_equity
    , f.sales_per_share as sales_per_share
    , f.ps_ratio as ps_ratio
from prices p
left join fundamentals f
    on p.ticker = f.ticker
    and p.date = f.date

