# MA Trading Strategy

    MA Crossing Setup for Multiple Market Asset

## Common Utils | common_utils.py

    Liquidity Status Condition and Ma Crossing Calculator

## SQLite stuffs

    https://alembic.sqlalchemy.org/en/latest/tutorial.html
    1. Write database table structure and relation in models directory
    2. Create table as defined model | here is example autogenerate command.
        alembic revision --autogenerate -m "create etf_holdings_ishare table"
    3. Upgrade model version into database
        alembic upgrade head
    4. Downgrade model version into database
        alembic downgrade head

    PS: 
    - Always review the auto-generated migration scripts before applying them. 
    - While Alembic is quite good at detecting changes, it's always a good practice to double-check.
    - Keep models consistent across an application. Using a single Base class for all models, it helps prevent discrepancies.
    - Regularly back up database, especially before applying migrations in a production environment.

    alembic upgrade head

## Update Market assets bar tables

    Update Bar Data
    Update all asset types with default settings:
    python update_market_asset_bar_ib.py

    Update only FOREX data:
    python update_market_asset_bar_ib.py --asset-type FOREX

    Update specific symbols for STOCK:
    bashCopypython update_market_asset_bar_ib.py --asset-type STOCK --symbols AAPL MSFT GOOGL

    Update with specific timeframes:
    python update_market_asset_bar_ib.py --asset-type COMMODITY --timeframes "1 hour" "4 hours"
    
    Update with custom look-back period:
    python update_market_asset_bar_ib.py --asset-type FOREX --days-back 30

## Market Updater script

    Update all assets with default settings:
    python market_updater.py

    Update specific stock symbols with custom timeframes:
    python market_updater.py --asset-type STOCK --symbols AAPL MSFT --timeframes 1min 5min

    Update crypto data for the last 7 days:
    python market_updater.py --asset-type CRYPTO --days-back 7

    Update all forex data with specific timeframes:
    python market_updater.py --asset-type FOREX --timeframes 1min 15min 1hour

    