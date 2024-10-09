import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TimeframeType(Base):
    __tablename__ = 'timeframe_type'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String, unique=True, nullable=False)

class StockMTFBar(Base):
    __tablename__ = 'stock_mtf_bar'

    id             = sa.Column(sa.Integer, primary_key=True)
    symbol         = sa.Column(sa.String, nullable=False)
    timestamp      = sa.Column(sa.DateTime, nullable=False)
    open           = sa.Column(sa.Float)
    high           = sa.Column(sa.Float)
    low            = sa.Column(sa.Float)
    close          = sa.Column(sa.Float)
    volume         = sa.Column(sa.Float)
    timeframe_type = sa.Column(sa.Integer, sa.ForeignKey('timeframe_type.id'), nullable=False)

    __table_args__ = (sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type'),)

class ForexMTFBar(Base):
    __tablename__ = 'forex_mtf_bar'

    id             = sa.Column(sa.Integer, primary_key=True)
    symbol         = sa.Column(sa.String, nullable=False)
    timestamp      = sa.Column(sa.DateTime, nullable=False)
    open           = sa.Column(sa.Float)
    high           = sa.Column(sa.Float)
    low            = sa.Column(sa.Float)
    close          = sa.Column(sa.Float)
    volume         = sa.Column(sa.Float)
    timeframe_type = sa.Column(sa.Integer, sa.ForeignKey('timeframe_type.id'), nullable=False)

    __table_args__ = (sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type'),)

class CommodityMTFBar(Base):
    __tablename__ = 'commodity_mtf_bar'

    id             = sa.Column(sa.Integer, primary_key=True)
    symbol         = sa.Column(sa.String, nullable=False)
    timestamp      = sa.Column(sa.DateTime, nullable=False)
    open           = sa.Column(sa.Float)
    high           = sa.Column(sa.Float)
    low            = sa.Column(sa.Float)
    close          = sa.Column(sa.Float)
    volume         = sa.Column(sa.Float)
    timeframe_type = sa.Column(sa.Integer, sa.ForeignKey('timeframe_type.id'), nullable=False)

    __table_args__ = (sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type'),)

class IndexMTFBar(Base):
    __tablename__ = 'index_mtf_bar'

    id             = sa.Column(sa.Integer, primary_key=True)
    symbol         = sa.Column(sa.String, nullable=False)
    timestamp      = sa.Column(sa.DateTime, nullable=False)
    open           = sa.Column(sa.Float)
    high           = sa.Column(sa.Float)
    low            = sa.Column(sa.Float)
    close          = sa.Column(sa.Float)
    volume         = sa.Column(sa.Float)
    timeframe_type = sa.Column(sa.Integer, sa.ForeignKey('timeframe_type.id'), nullable=False)

    __table_args__ = (sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type'),)

class FutureMTFBar(Base):
    __tablename__ = 'future_mtf_bar'

    id             = sa.Column(sa.Integer, primary_key=True)
    symbol         = sa.Column(sa.String, nullable=False)
    timestamp      = sa.Column(sa.DateTime, nullable=False)
    open           = sa.Column(sa.Float)
    high           = sa.Column(sa.Float)
    low            = sa.Column(sa.Float)
    close          = sa.Column(sa.Float)
    volume         = sa.Column(sa.Float)
    timeframe_type = sa.Column(sa.Integer, sa.ForeignKey('timeframe_type.id'), nullable=False)

    __table_args__ = (sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type'),)

class OptionMTFBar(Base):
    __tablename__ = 'option_mtf_bar'

    id             = sa.Column(sa.Integer, primary_key=True)
    symbol         = sa.Column(sa.String, nullable=False)
    timestamp      = sa.Column(sa.DateTime, nullable=False)
    open           = sa.Column(sa.Float)
    high           = sa.Column(sa.Float)
    low            = sa.Column(sa.Float)
    close          = sa.Column(sa.Float)
    volume         = sa.Column(sa.Float)
    timeframe_type = sa.Column(sa.Integer, sa.ForeignKey('timeframe_type.id'), nullable=False)

    __table_args__ = (sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type'),)

class CFDMTFBar(Base):
    __tablename__ = 'cfd_mtf_bar'

    id             = sa.Column(sa.Integer, primary_key=True)
    symbol         = sa.Column(sa.String, nullable=False)
    timestamp      = sa.Column(sa.DateTime, nullable=False)
    open           = sa.Column(sa.Float)
    high           = sa.Column(sa.Float)
    low            = sa.Column(sa.Float)
    close          = sa.Column(sa.Float)
    volume         = sa.Column(sa.Float)
    timeframe_type = sa.Column(sa.Integer, sa.ForeignKey('timeframe_type.id'), nullable=False)

    __table_args__ = (sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type'),)

class BondMTFBar(Base):
    __tablename__ = 'bond_mtf_bar'

    id             = sa.Column(sa.Integer, primary_key=True)
    symbol         = sa.Column(sa.String, nullable=False)
    timestamp      = sa.Column(sa.DateTime, nullable=False)
    open           = sa.Column(sa.Float)
    high           = sa.Column(sa.Float)
    low            = sa.Column(sa.Float)
    close          = sa.Column(sa.Float)
    volume         = sa.Column(sa.Float)
    timeframe_type = sa.Column(sa.Integer, sa.ForeignKey('timeframe_type.id'), nullable=False)

    __table_args__ = (sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type'),)

class CryptoMTFBar(Base):
    __tablename__ = 'crypto_mtf_bar'

    id             = sa.Column(sa.Integer, primary_key=True)
    symbol         = sa.Column(sa.String, nullable=False)
    timestamp      = sa.Column(sa.DateTime, nullable=False)
    open           = sa.Column(sa.Float)
    high           = sa.Column(sa.Float)
    low            = sa.Column(sa.Float)
    close          = sa.Column(sa.Float)
    volume         = sa.Column(sa.Float)
    timeframe_type = sa.Column(sa.Integer, sa.ForeignKey('timeframe_type.id'), nullable=False)

    __table_args__ = (sa.UniqueConstraint('symbol', 'timestamp', 'timeframe_type'),)