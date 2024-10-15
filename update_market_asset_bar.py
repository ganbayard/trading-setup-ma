import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

import pandas as pd
from sqlalchemy import create_engine, select, delete, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.sqlite import insert

from data_sources import BinanceCryptoLoader
from models.market_models import CryptoMTFBar, TimeframeType
from config import TIMEFRAMES, DURATION_MAP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///market_assets.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

async def get_timeframe_type_id(session, timeframe: str) -> int:
    result = session.execute(select(TimeframeType.id).where(TimeframeType.name == timeframe)).scalar_one_or_none()
    if result is None:
        raise ValueError(f"Timeframe {timeframe} not found in TimeframeType table")
    return result

async def delete_existing_data(session, symbol: str, timeframe_type_id: int, start_date: datetime, end_date: datetime):
    try:
        delete_stmt = delete(CryptoMTFBar).where(
            CryptoMTFBar.symbol == symbol,
            CryptoMTFBar.timeframe_type == timeframe_type_id,
            CryptoMTFBar.timestamp.between(start_date, end_date)
        )
        result = session.execute(delete_stmt)
        session.commit()
        logger.info(f"Deleted {result.rowcount} existing rows for {symbol} with timeframe_type_id {timeframe_type_id}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error deleting existing data for {symbol}: {str(e)}")

async def upsert_crypto_data(session, symbol: str, timeframe: str, df: pd.DataFrame, timeframe_type_id: int):
    try:
        logger.info(f"Upserting data for {symbol} with timeframe {timeframe}. DataFrame shape: {df.shape}")
        logger.info(f"DataFrame date range: {df.index.min()} to {df.index.max()}")
        for index, row in df.iterrows():
            stmt = insert(CryptoMTFBar).values(
                symbol=symbol,
                timestamp=index,
                open=row['Open'],
                high=row['High'],
                low=row['Low'],
                close=row['Close'],
                volume=row['Volume'],
                timeframe_type=timeframe_type_id
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['symbol', 'timestamp', 'timeframe_type'],
                set_=dict(
                    open=stmt.excluded.open,
                    high=stmt.excluded.high,
                    low=stmt.excluded.low,
                    close=stmt.excluded.close,
                    volume=stmt.excluded.volume
                )
            )
            session.execute(stmt)
        session.commit()
        logger.info(f"Upserted {len(df)} rows for {symbol} with timeframe {timeframe}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error upserting data for {symbol} with timeframe {timeframe}: {str(e)}")

async def update_crypto_data(symbols: List[str], timeframes: List[str]):
    loader = BinanceCryptoLoader()
    end_date = datetime.now()
    
    session = Session()
    try:
        for timeframe in timeframes:
            logger.info(f"Processing timeframe: {timeframe}")
            timeframe_type_id = await get_timeframe_type_id(session, timeframe)
            duration = DURATION_MAP[timeframe]
            duration_days = int(duration.split()[0])
            start_date = end_date - timedelta(days=duration_days)
            
            logger.info(f"Fetching data from {start_date} to {end_date} for timeframe {timeframe}")
            
            data = await loader.load_data(
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d"),
                symbols,
                timeframe
            )
            
            for symbol, df in data.items():
                if df is not None and not df.empty:
                    logger.info(f"Received data for {symbol} with timeframe {timeframe}. Shape: {df.shape}")
                    logger.info(f"Data range: {df.index.min()} to {df.index.max()}")
                    # Upsert new data
                    await upsert_crypto_data(session, symbol, timeframe, df, timeframe_type_id)
                else:
                    logger.warning(f"No data available for {symbol} with timeframe {timeframe}")
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        session.close()

async def main():
    try:
        # Load symbols from the file
        with open('symbols/market_assets/crypto.txt', 'r') as f:
            symbols = [symbol.strip() for symbol in f.read().strip().split(',')]
        
        logger.info(f"Loaded {len(symbols)} symbols: {', '.join(symbols)}")
        logger.info(f"Timeframes to process: {', '.join(TIMEFRAMES)}")
        
        await update_crypto_data(symbols, TIMEFRAMES)
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
