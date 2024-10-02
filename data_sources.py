import os
import random
import logging
from typing import List, Dict
import pandas as pd
from abc import ABC, abstractmethod
from ib_async import *
from ib_async import Stock, Option, Future, Index, Forex, CFD, Commodity, Bond
import concurrent.futures
from binance.client import Client as BinanceClient

from PyQt5.QtCore import QObject

from config import SOCKET, MARKET_ASSET_TYPES, TIMEFRAMES, DURATION_MAP
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import asyncio

load_dotenv()

binance_api_key = os.getenv('BINANCE_API_KEY')
binance_api_secret = os.getenv('BINANCE_API_SECRET')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseDataLoader(ABC):
    def __init__(self, max_workers=6):
        self.max_workers = max_workers
        self.symbols = self.load_symbols()

    @abstractmethod
    def load_symbols(self) -> List[str]:
        pass

    @abstractmethod
    async def fetch_symbol_data(self, symbol: str, start_date: str, end_date: str, interval='1d') -> pd.DataFrame:
        pass

    @abstractmethod
    async def load_data(self, start_date: str, end_date: str, symbols=None, interval='1d') -> Dict[str, pd.DataFrame]:
        pass

class IBBaseLoader:
    def __init__(self, max_workers=16, contract_type='STOCK'):
        self.contract_type = contract_type.upper()
        self.ib = IB()
        self.max_workers = max_workers
        self.symbols = self.load_symbols()

    def load_symbols(self) -> List[str]:
        file_path = MARKET_ASSET_TYPES.get(self.contract_type, '')
        if not file_path:
            raise ValueError(f"No symbol file found for contract type: {self.contract_type}")
        with open(file_path, 'r') as f:
            return [symbol.strip() for symbol in f.read().strip().split(',')]

    async def connect(self):
        if not self.ib.isConnected():
            try:
                await asyncio.wait_for(
                    self.ib.connectAsync(SOCKET['HOST'], SOCKET['PORT'], clientId=random.randint(1, 9999)),
                    timeout=30
                )
                self.ib.reqMarketDataType(4)
                logger.info("Successfully connected to Interactive Brokers")
            except asyncio.TimeoutError:
                logger.error("Timeout while connecting to Interactive Brokers")
                raise ConnectionError("Failed to connect to Interactive Brokers: Timeout")
            except Exception as e:
                logger.error(f"Failed to connect to Interactive Brokers: {str(e)}")
                raise ConnectionError(f"Failed to connect to Interactive Brokers: {str(e)}")

    def create_contract(self, symbol: str):
        if self.contract_type == 'STOCK':
            return Stock(symbol, 'SMART', 'USD')
        elif self.contract_type == 'OPTION':
            return Option(symbol, '20241026', 150, 'C', 'SMART')
        elif self.contract_type == 'FUTURE':
            return Future(symbol, '202412', 'GLOBEX')
        elif self.contract_type == 'INDEX':
            return Index(symbol, 'SMART', 'USD')
        elif self.contract_type == 'FOREX':
            return Forex(symbol, exchange='IDEALPRO')
        elif self.contract_type == 'CFD':
            return CFD(symbol, 'SMART', 'USD')
        elif self.contract_type == 'COMMODITY':
            return Commodity(symbol, 'SMART', 'USD')
        elif self.contract_type == 'BOND':
            return Bond(secIdType='ISIN', secId='US03076KAA60')
        else:
            raise ValueError(f"Unsupported contract type: {self.contract_type}")

    async def fetch_symbol_data(self, symbol: str, start_date: str, end_date: str, interval='1 hour') -> pd.DataFrame:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not self.ib.isConnected():
                    await self.connect()

                contract = self.create_contract(symbol)

                duration_str = DURATION_MAP.get(interval, '30 D')
                end_datetime = datetime.strptime(end_date, "%Y%m%d").replace(tzinfo=pytz.UTC)
                formatted_end_date = end_datetime.strftime("%Y%m%d %H:%M:%S")

                print(f"Fetching data for {symbol} with interval: {interval}")

                bars = await asyncio.wait_for(
                    self.ib.reqHistoricalDataAsync(
                        contract,
                        endDateTime=formatted_end_date,
                        durationStr=duration_str,
                        barSizeSetting=interval,
                        whatToShow='MIDPOINT',
                        useRTH=True,
                        formatDate=2
                    ),
                    timeout=60
                )

                if not bars:
                    logger.warning(f"No data found for {symbol} with interval {interval}")
                    return pd.DataFrame()

                df = util.df(bars)
                if df.empty:
                    logger.warning(f"Empty DataFrame for {symbol} with interval {interval}")
                    return df

                df.set_index('date', inplace=True)
                df.index = pd.to_datetime(df.index)
                df = df[['open', 'high', 'low', 'close', 'volume']]
                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

                df['Volume'] = df['Volume'].replace(-1, float('nan'))
                logger.info(f"Successfully fetched data for {symbol}: {len(df)} rows")
                return df.sort_index()

            except asyncio.TimeoutError:
                logger.warning(f"Timeout while fetching data for {symbol} with interval {interval}. Attempt {attempt + 1} of {max_retries}")
                if attempt == max_retries - 1:
                    logger.error(f"Max retries reached. Failed to fetch data for {symbol} with interval {interval}")
                    return pd.DataFrame()
            except Exception as e:
                logger.error(f"Failed to fetch data from IB for {symbol}: {str(e)}")
                return pd.DataFrame()

        return pd.DataFrame() 

    async def load_data(self, start_date: str, end_date: str, symbols=None, interval='1d') -> Dict[str, pd.DataFrame]:
        if symbols is None:
            symbols = self.symbols
        if isinstance(symbols, str):
            symbols = [symbols]
        results = {}
        for symbol in symbols:
            try:
                df = await self.fetch_symbol_data(symbol, start_date, end_date, interval)
                results[symbol] = df
                if not df.empty:
                    logger.info(f"Successfully loaded data for {symbol}: {len(df)} rows")
                else:
                    logger.warning(f"Empty DataFrame loaded for {symbol}")
            except Exception as e:
                logger.error(f"Error loading data for {symbol}: {str(e)}")
                results[symbol] = pd.DataFrame()
        return results

    async def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            logger.info("Disconnected from Interactive Brokers")

    def __del__(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            logger.info("Disconnected from Interactive Brokers in destructor")

class BinanceCryptoLoader(BaseDataLoader):
    def __init__(self, max_workers=6):
        super().__init__(max_workers)
        self.client = BinanceClient(api_key=binance_api_key, api_secret=binance_api_secret)

    def load_symbols(self) -> List[str]:
        file_path = MARKET_ASSET_TYPES.get('CRYPTO', '')
        if not file_path:
            raise ValueError("No symbol file found for crypto")
        with open(file_path, 'r') as f:
            return [symbol.strip() for symbol in f.read().strip().split(',')]

    async def fetch_symbol_data(self, symbol: str, start_date: str, end_date: str, interval='1 day') -> pd.DataFrame:
        try:
            if symbol.endswith('USD') and symbol != 'USDT':
                symbol = symbol[:-3] + 'USDT'

            start_ts = int(datetime.strptime(start_date, "%Y%m%d").replace(tzinfo=pytz.UTC).timestamp() * 1000)
            end_ts = int(datetime.strptime(end_date, "%Y%m%d").replace(tzinfo=pytz.UTC).timestamp() * 1000)

            # Convert interval to Binance format
            binance_interval = interval.replace(' mins', 'm').replace(' hour', 'h').replace(' day', 'd').replace('1 W', '1w')

            klines = self.client.get_historical_klines(
                symbol, 
                binance_interval,
                start_ts,
                end_ts
            )
            
            if not klines:
                logger.warning(f"No data returned for {symbol} between {start_date} and {end_date}")
                return pd.DataFrame()

            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']]
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            df = df.astype(float)
            print(df.head(2))
            return df
        except Exception as e:
            logger.error(f"Failed to fetch data from Binance for {symbol}: {str(e)}")
            raise

    async def load_data(self, start_date: str, end_date: str, symbols=None, interval='1d') -> Dict[str, pd.DataFrame]:
        if symbols is None:
            symbols = self.symbols
        if isinstance(symbols, str):
            symbols = [symbols]
        results = {}
        for symbol in symbols:
            try:
                df = await self.fetch_symbol_data(symbol, start_date, end_date, interval)
                results[symbol] = df
                logger.info(f"Successfully loaded data for {symbol}")
            except Exception as e:
                logger.error(f"Error loading data for {symbol}: {str(e)}")
                results[symbol] = None
        return results

def get_data_loader(asset_type: str) -> BaseDataLoader:
    asset_type = asset_type.upper()
    
    if asset_type in MARKET_ASSET_TYPES:
        if asset_type == 'CRYPTO':
            return BinanceCryptoLoader()
        else:
            return IBBaseLoader(contract_type=asset_type)
    else:
        raise ValueError(f"Unsupported asset type: {asset_type}")

# async def main():
#     loader = None
#     try:
#         loader = get_data_loader('STOCK')
#         data = loader.load_data('20230101', '20230930')
        
#         success_count = 0
#         no_data_count = 0
#         failure_count = 0
        
#         for symbol, df in data.items():
#             if isinstance(df, pd.DataFrame) and not df.empty:
#                 print(f"{symbol}: {len(df)} rows") 
#                 success_count += 1
#             elif df is None:
#                 print(f"{symbol}: Failed to retrieve data")
#                 failure_count += 1
#             else:
#                 print(f"{symbol}: No data available")
#                 no_data_count += 1
        
#         print(f"\nSummary:")
#         print(f"Successful data retrievals: {success_count}")
#         print(f"Symbols with no data: {no_data_count}")
#         print(f"Failed data retrievals: {failure_count}")
        
#         if no_data_count > 0 or failure_count > 0:
#             print("\nPossible reasons for no data or failures:")
#             print("1. The specified date range might not have data for some symbols")
#             print("2. Connection issues with Interactive Brokers")
#             print("3. Insufficient permissions for certain symbols")
#             print("4. Symbol not recognized or no longer active")
#     except Exception as e:
#         print(f"An error occurred while running the script: {str(e)}")
#     finally:
#         if loader and isinstance(loader, IBBaseLoader):
#             await loader.disconnect()
#         print("Script execution completed.")

# if __name__ == "__main__":
#     main()