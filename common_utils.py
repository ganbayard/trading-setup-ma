import logging
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from models.market_models import (
    StockMTFBar, ForexMTFBar, CommodityMTFBar, IndexMTFBar,
    FutureMTFBar, OptionMTFBar, CFDMTFBar, BondMTFBar, CryptoMTFBar,
    TimeframeType, MarketAssetType
)

logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///market_assets.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

ASSET_MODEL_MAP = {
    'STOCK': StockMTFBar,
    'FOREX': ForexMTFBar,
    'COMMODITY': CommodityMTFBar,
    'INDEX': IndexMTFBar,
    'FUTURE': FutureMTFBar,
    'OPTION': OptionMTFBar,
    'CFD': CFDMTFBar,
    'BOND': BondMTFBar,
    'CRYPTO': CryptoMTFBar
}

def get_timeframe_type_id(session, timeframe: str) -> int:
    """Get the timeframe type ID from the database."""
    result = session.execute(
        select(TimeframeType.id).where(TimeframeType.name == timeframe)
    ).scalar_one_or_none()
    return result

def fetch_market_asset_data(asset_type: str, symbol: str = None, 
                          timeframe: str = '1 hour', days_back: int = 60):
    """
    Fetch market asset data from the database.
    
    Args:
        asset_type (str): Type of market asset (STOCK, FOREX, etc.)
        symbol (str, optional): Specific symbol to fetch. If None, fetches all symbols.
        timeframe (str): Timeframe to fetch data for
        days_back (int): Number of days of historical data to fetch
        
    Returns:
        dict: Dictionary mapping symbols to their DataFrame of historical data
    """
    session = Session()
    try:
        model_class = ASSET_MODEL_MAP.get(asset_type.upper())
        if not model_class:
            logger.error(f"Unsupported asset type: {asset_type}")
            return {}

        timeframe_type_id = get_timeframe_type_id(session, timeframe)
        if timeframe_type_id is None:
            logger.error(f"Invalid timeframe: {timeframe}")
            return {}

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        query = select(model_class).where(
            and_(
                model_class.timeframe_type == timeframe_type_id,
                model_class.timestamp.between(start_date, end_date)
            )
        )

        if symbol:
            query = query.where(model_class.symbol == symbol)

        result = session.execute(query)
        rows = result.fetchall()

        if not rows:
            logger.warning(f"No data found for {asset_type}" + 
                         (f" symbol {symbol}" if symbol else ""))
            logger.warning(f"Please update the {asset_type.lower()}_mtf_bar table using the update script")
            return {}

        data = {}
        for row in rows:
            row = row[0]
            symbol = row.symbol
            
            if symbol not in data:
                data[symbol] = []
                
            data[symbol].append({
                'timestamp': row.timestamp,
                'Open': row.open,
                'High': row.high,
                'Low': row.low,
                'Close': row.close,
                'Volume': row.volume
            })

        for symbol in data:
            df = pd.DataFrame(data[symbol])
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            data[symbol] = df

        return data

    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching {asset_type} data: {str(e)}")
        return {}
    finally:
        session.close()

def calculate_ma_cross(df):
    """Calculate moving average crossover points."""
    if df is None or df.empty:
        return None, None

    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    ma_cross_support = None
    ma_cross_resistance = None
    
    for i in range(len(df) - 1, 0, -1):
        if df['MA20'].iloc[i] < df['MA200'].iloc[i] and df['MA20'].iloc[i-1] >= df['MA200'].iloc[i-1]:
            if ma_cross_resistance is None:
                ma_cross_resistance = max(df['MA20'].iloc[i], df['MA200'].iloc[i])
        elif df['MA20'].iloc[i] > df['MA200'].iloc[i] and df['MA20'].iloc[i-1] <= df['MA200'].iloc[i-1]:
            if ma_cross_support is None:
                ma_cross_support = min(df['MA20'].iloc[i], df['MA200'].iloc[i])
        
        if ma_cross_support is not None and ma_cross_resistance is not None:
            break

    return ma_cross_support, ma_cross_resistance