# common_utils.py
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
    """Get the timeframe type ID with error handling."""
    try:
        result = session.execute(
            select(TimeframeType.id).where(TimeframeType.name == timeframe)
        ).scalar_one_or_none()
        
        if result is None:
            logger.error(f"Timeframe {timeframe} not found in TimeframeType table")
        
        return result
    except SQLAlchemyError as e:
        logger.error(f"Database error while getting timeframe ID: {str(e)}")
        return None

def process_market_data(rows, symbol=None):
    """Process and clean market data."""
    try:
        data = {}
        for row in rows:
            row = row[0]
            symbol = row.symbol
            
            if symbol not in data:
                data[symbol] = []
            
            # Ensure no None values in data
            data[symbol].append({
                'timestamp': row.timestamp,
                'Open': row.open if row.open is not None else 0.0,
                'High': row.high if row.high is not None else 0.0,
                'Low': row.low if row.low is not None else 0.0,
                'Close': row.close if row.close is not None else 0.0,
                'Volume': row.volume if row.volume is not None else 0.0
            })

        for symbol in data:
            df = pd.DataFrame(data[symbol])
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            
            # Clean numeric data
            numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Fill NaN values
            df['Volume'] = df['Volume'].fillna(0)
            df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].fillna(method='ffill')
            
            data[symbol] = df

        return data
    except Exception as e:
        logger.error(f"Error processing market data: {str(e)}")
        return {}

def fetch_market_asset_data(asset_type: str, symbol: str = None, 
                          timeframe: str = '1 hour', days_back: int = 60):
    """
    Fetch market asset data with improved error handling and data cleaning.
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
            return {}

        return process_market_data(rows, symbol)

    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching {asset_type} data: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error while fetching {asset_type} data: {str(e)}")
        return {}
    finally:
        session.close()

def calculate_ma_cross(df):
    """Calculate moving average crossover points with error handling."""
    try:
        if df is None or df.empty:
            return None, None

        df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
        df['MA200'] = df['Close'].rolling(window=200, min_periods=1).mean()
        
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
    except Exception as e:
        logger.error(f"Error calculating MA cross: {str(e)}")
        return None, None