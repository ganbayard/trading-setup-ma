import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Type
import argparse

import pandas as pd
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.sqlite import insert

from data_sources import IBBaseLoader
from models.market_models import (
    ForexMTFBar, 
    StockMTFBar, 
    CommodityMTFBar,
    IndexMTFBar,
    FutureMTFBar,
    OptionMTFBar,
    CFDMTFBar,
    BondMTFBar,
    TimeframeType,
    Base
)
from config import TIMEFRAMES, DURATION_MAP, MARKET_ASSET_TYPES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///market_assets.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Map asset types to their corresponding model classes
ASSET_MODEL_MAP = {
    'FOREX': ForexMTFBar,
    'STOCK': StockMTFBar,
    'COMMODITY': CommodityMTFBar,
    'INDEX': IndexMTFBar,
    'FUTURE': FutureMTFBar,
    'OPTION': OptionMTFBar,
    'CFD': CFDMTFBar,
    'BOND': BondMTFBar
}

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Update market asset bar data from Interactive Brokers.')
    
    parser.add_argument(
        '--asset-type',
        type=str,
        choices=['FOREX', 'STOCK', 'COMMODITY', 'INDEX', 'FUTURE', 'OPTION', 'CFD', 'BOND', 'ALL'],
        default='ALL',
        help='Type of asset to update (default: ALL)'
    )
    
    parser.add_argument(
        '--symbols',
        type=str,
        nargs='+',
        help='Specific symbols to update. If not provided, all symbols from the corresponding file will be used.'
    )
    
    parser.add_argument(
        '--timeframes',
        type=str,
        nargs='+',
        choices=TIMEFRAMES,
        default=TIMEFRAMES,
        help='Specific timeframes to update (default: all timeframes)'
    )
    
    parser.add_argument(
        '--days-back',
        type=int,
        help='Number of days to look back for data. Overrides the default duration map.'
    )
    
    return parser.parse_args()

async def get_timeframe_type_id(session, timeframe: str) -> int:
    """Get the timeframe type ID from the database."""
    result = session.execute(
        select(TimeframeType.id).where(TimeframeType.name == timeframe)
    ).scalar_one_or_none()
    
    if result is None:
        raise ValueError(f"Timeframe {timeframe} not found in TimeframeType table")
    return result

async def delete_existing_data(session, model_class: Type[Base], symbol: str,  # type: ignore
                             timeframe_type_id: int, start_date: datetime, 
                             end_date: datetime):
    """Delete existing data for the given symbol and timeframe."""
    try:
        delete_stmt = delete(model_class).where(
            model_class.symbol == symbol,
            model_class.timeframe_type == timeframe_type_id,
            model_class.timestamp.between(start_date, end_date)
        )
        result = session.execute(delete_stmt)
        session.commit()
        logger.info(f"Deleted {result.rowcount} existing rows for {symbol} "
                   f"with timeframe_type_id {timeframe_type_id}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error deleting existing data for {symbol}: {str(e)}")
        raise

async def upsert_market_data(session, model_class: Type[Base], symbol: str,  # type: ignore
                           timeframe: str, df: pd.DataFrame, 
                           timeframe_type_id: int):
    """Upsert market data into the database."""
    try:
        logger.info(f"Upserting data for {symbol} with timeframe {timeframe}. "
                   f"DataFrame shape: {df.shape}")
        
        for index, row in df.iterrows():
            stmt = insert(model_class).values(
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
        raise

def load_symbols(asset_type: str, provided_symbols: List[str] = None) -> List[str]:
    """Load symbols from file or use provided symbols."""
    if provided_symbols:
        return provided_symbols
    
    file_path = MARKET_ASSET_TYPES.get(asset_type)
    if not file_path:
        raise ValueError(f"No symbol file found for asset type: {asset_type}")
    
    with open(file_path, 'r') as f:
        return [symbol.strip() for symbol in f.read().strip().split(',')]

async def update_market_data(asset_type: str, symbols: List[str], 
                           timeframes: List[str], days_back: int = None):
    """Update market data for the specified asset type."""
    model_class = ASSET_MODEL_MAP.get(asset_type.upper())
    if not model_class:
        raise ValueError(f"Unsupported asset type: {asset_type}")

    loader = IBBaseLoader(contract_type=asset_type)
    end_date = datetime.now()
    
    session = Session()
    try:
        await loader.connect()
        
        for timeframe in timeframes:
            logger.info(f"Processing timeframe: {timeframe}")
            timeframe_type_id = await get_timeframe_type_id(session, timeframe)
            
            if days_back:
                start_date = end_date - timedelta(days=days_back)
            else:
                duration = DURATION_MAP[timeframe]
                duration_days = int(duration.split()[0])
                start_date = end_date - timedelta(days=duration_days)
            
            logger.info(f"Fetching data from {start_date} to {end_date} "
                       f"for timeframe {timeframe}")
            
            data = await loader.load_data(
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d"),
                symbols,
                timeframe
            )
            
            for symbol, df in data.items():
                if df is not None and not df.empty:
                    logger.info(f"Received data for {symbol} with timeframe {timeframe}. "
                              f"Shape: {df.shape}")
                    await delete_existing_data(
                        session, model_class, symbol, timeframe_type_id,
                        df.index.min(), df.index.max()
                    )
                    await upsert_market_data(
                        session, model_class, symbol, timeframe, df, timeframe_type_id
                    )
                else:
                    logger.warning(f"No data available for {symbol} with timeframe {timeframe}")
    
    except Exception as e:
        logger.error(f"Error updating {asset_type} data: {str(e)}")
        raise
    finally:
        await loader.disconnect()
        session.close()

async def main():
    """Main function to update market asset data based on command line arguments."""
    args = parse_arguments()
    
    if args.asset_type == 'ALL':
        asset_types = list(ASSET_MODEL_MAP.keys())
    else:
        asset_types = [args.asset_type]
    
    for asset_type in asset_types:
        try:
            symbols = load_symbols(asset_type, args.symbols)
            
            logger.info(f"Processing {asset_type}")
            logger.info(f"Processing {len(symbols)} symbols: {', '.join(symbols)}")
            logger.info(f"Timeframes to process: {', '.join(args.timeframes)}")
            
            await update_market_data(
                asset_type, 
                symbols, 
                args.timeframes,
                args.days_back
            )
            
        except Exception as e:
            logger.error(f"Error processing {asset_type}: {str(e)}")
            continue 

if __name__ == "__main__":
    asyncio.run(main())