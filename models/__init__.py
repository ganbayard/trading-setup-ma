from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from .market_models  import Base, StockMTFBar, CFDMTFBar, CommodityMTFBar, CryptoMTFBar, OptionMTFBar, ForexMTFBar, BondMTFBar
engine = create_engine('sqlite:///market_assets.db')
Session = sessionmaker(bind=engine)

__all__ = [
    'Base', 'StockMTFBar', 'CFDMTFBar', 'CommodityMTFBar', 'CryptoMTFBar', 
    'OptionMTFBar', 'ForexMTFBar', 'BondMTFBar'
    ]