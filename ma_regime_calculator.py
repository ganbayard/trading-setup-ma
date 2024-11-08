from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

from models.market_models import (
    MaCrossTab, TimeframeType, MarketAssetType,
    ForexMTFBar, StockMTFBar, CryptoMTFBar, CommodityMTFBar,
    IndexMTFBar, FutureMTFBar, OptionMTFBar, CFDMTFBar, BondMTFBar
)

logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///market_assets.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

ASSET_MODEL_MAP = {
    'FOREX': ForexMTFBar,
    'STOCK': StockMTFBar,
    'CRYPTO': CryptoMTFBar,
    'COMMODITY': CommodityMTFBar,
    'INDEX': IndexMTFBar,
    'FUTURE': FutureMTFBar,
    'OPTION': OptionMTFBar,
    'CFD': CFDMTFBar,
    'BOND': BondMTFBar
}

class MarketRegimeCalculator:
    def __init__(self):
        self.session = Session()

    def calculate_ma_regime(self, df: pd.DataFrame) -> Tuple[Optional[float], Optional[float], str, float, float]:
        """
        Calculate MA regime based on 20/200 cross
        Returns: (support, resistance, liquidity_status, last_price, change_percent)
        """
        if df is None or df.empty:
            return None, None, "UNKNOWN", 0.0, 0.0
            
        df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
        df['MA200'] = df['Close'].rolling(window=200, min_periods=1).mean()
        
        ma_cross_support = None
        ma_cross_resistance = None
        
        last_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2] if len(df) > 1 else last_price
        change_percent = ((last_price - prev_price) / prev_price * 100) if prev_price != 0 else 0
        
        # Find most recent crosses
        for i in range(len(df) - 1, 0, -1):
            if df['MA20'].iloc[i] < df['MA200'].iloc[i] and df['MA20'].iloc[i-1] >= df['MA200'].iloc[i-1]:
                if ma_cross_resistance is None:
                    ma_cross_resistance = max(df['MA20'].iloc[i], df['MA200'].iloc[i])
            elif df['MA20'].iloc[i] > df['MA200'].iloc[i] and df['MA20'].iloc[i-1] <= df['MA200'].iloc[i-1]:
                if ma_cross_support is None:
                    ma_cross_support = min(df['MA20'].iloc[i], df['MA200'].iloc[i])
            
            if ma_cross_support is not None and ma_cross_resistance is not None:
                break
        
        # Determine liquidity status
        if last_price > df['MA200'].iloc[-1]:
            if df['MA20'].iloc[-1] > df['MA200'].iloc[-1]:
                liquidity_status = "STRONG_BULLISH"
            else:
                liquidity_status = "BULLISH"
        elif last_price < df['MA200'].iloc[-1]:
            if df['MA20'].iloc[-1] < df['MA200'].iloc[-1]:
                liquidity_status = "STRONG_BEARISH"
            else:
                liquidity_status = "BEARISH"
        else:
            liquidity_status = "NEUTRAL"
            
        return ma_cross_support, ma_cross_resistance, liquidity_status, last_price, change_percent

    def get_market_data(self, asset_type: str, symbol: str, timeframe: str) -> pd.DataFrame:
        """Fetch market data for analysis"""
        try:
            model_class = ASSET_MODEL_MAP.get(asset_type.upper())
            if not model_class:
                logger.error(f"Unsupported asset type: {asset_type}")
                return pd.DataFrame()
                
            timeframe_type_id = self.session.execute(
                select(TimeframeType.id).where(TimeframeType.name == timeframe)
            ).scalar_one_or_none()
            
            if not timeframe_type_id:
                logger.error(f"Invalid timeframe: {timeframe}")
                return pd.DataFrame()
                
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)
            
            query = select(model_class).where(
                and_(
                    model_class.symbol == symbol,
                    model_class.timeframe_type == timeframe_type_id,
                    model_class.timestamp.between(start_date, end_date)
                )
            ).order_by(model_class.timestamp)
            
            result = self.session.execute(query)
            rows = result.fetchall()
            
            if not rows:
                return pd.DataFrame()
                
            df = pd.DataFrame([{
                'timestamp': row[0].timestamp,
                'Open': row[0].open,
                'High': row[0].high,
                'Low': row[0].low,
                'Close': row[0].close,
                'Volume': row[0].volume
            } for row in rows])
            
            df.set_index('timestamp', inplace=True)
            return df
            
        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            return pd.DataFrame()

    def get_regime_data(self, asset_type: str, symbol: str, timeframe: str) -> Dict:
        """Get complete regime data for a symbol"""
        try:
            df = self.get_market_data(asset_type, symbol, timeframe)
            if df.empty:
                return {
                    'symbol': symbol,
                    'last_price': 0.0,
                    'change_percent': 0.0,
                    'ma_cross_support': None,
                    'ma_cross_resistance': None,
                    'liquidity_status': 'UNKNOWN'
                }
            
            support, resistance, status, last_price, change_percent = self.calculate_ma_regime(df)
            
            return {
                'symbol': symbol,
                'last_price': last_price,
                'change_percent': change_percent,
                'ma_cross_support': support,
                'ma_cross_resistance': resistance,
                'liquidity_status': status
            }
            
        except Exception as e:
            logger.error(f"Error calculating regime data for {symbol}: {str(e)}")
            return None

    def update_ma_regime(self, asset_type: str, symbol: str, timeframe: str) -> bool:
        """Update MA regime in database"""
        try:
            market_asset_type_id = self.session.execute(
                select(MarketAssetType.id).where(MarketAssetType.name == asset_type.upper())
            ).scalar_one_or_none()
            
            timeframe_type_id = self.session.execute(
                select(TimeframeType.id).where(TimeframeType.name == timeframe)
            ).scalar_one_or_none()
            
            if not market_asset_type_id or not timeframe_type_id:
                return False
            
            regime_data = self.get_regime_data(asset_type, symbol, timeframe)
            if not regime_data:
                return False
            
            ma_cross_data = self.session.execute(
                select(MaCrossTab).where(
                    and_(
                        MaCrossTab.symbol == symbol,
                        MaCrossTab.market_assets_type == market_asset_type_id,
                        MaCrossTab.timeframe_type == timeframe_type_id
                    )
                )
            ).scalar_one_or_none()
            
            if ma_cross_data:
                ma_cross_data.ma_cross_support = regime_data['ma_cross_support']
                ma_cross_data.ma_cross_resistance = regime_data['ma_cross_resistance']
                ma_cross_data.liquidity_status = regime_data['liquidity_status']
            else:
                ma_cross_data = MaCrossTab(
                    symbol=symbol,
                    market_assets_type=market_asset_type_id,
                    timeframe_type=timeframe_type_id,
                    ma_cross_support=regime_data['ma_cross_support'],
                    ma_cross_resistance=regime_data['ma_cross_resistance'],
                    liquidity_status=regime_data['liquidity_status']
                )
                self.session.add(ma_cross_data)
                
            self.session.commit()
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating MA regime: {str(e)}")
            return False

    def __del__(self):
        """Cleanup database session"""
        try:
            self.session.close()
        except:
            pass