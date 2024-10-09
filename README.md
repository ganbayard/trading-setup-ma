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
