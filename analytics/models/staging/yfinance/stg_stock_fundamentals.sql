with source as (
    select * from {{ source('yfinance', 'raw_stock_fundamentals') }}
)

select
    ticker as ticker
    , revenue_growth_yoy as revenue_growth_yoy
    , operating_margin as operating_margin
    , roe as return_on_equity
    , sales_per_share as sales_per_share
    , ps_ratio as ps_ratio
    , last_updated_date as date
from source
