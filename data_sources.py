import os
import asyncio
import random
import logging
from typing import List, Dict
import pandas as pd
from abc import ABC, ABCMeta, abstractmethod
from ib_async import *
from ib_async import Stock, Option, Future, Index, Forex, CFD, Commodity, Bond
import concurrent.futures
from binance.client import Client as BinanceClient

from PyQt5.QtCore import QObject

from config import SOCKET, MARKET_ASSET_TYPES, TIMEFRAMES, DURATION_MAP
from dotenv import load_dotenv
import datetime
import pytz

load_dotenv()

binance_api_key = os.getenv('BINANCE_API_KEY')
binance_api_secret = os.getenv('BINANCE_API_SECRET')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QObjectABCMeta(type(QObject), ABCMeta):
    pass

class BaseDataLoader(QObject, ABC, metaclass=QObjectABCMeta):
    def __init__(self, max_workers=6):
        super().__init__()
        self.max_workers = max_workers
        self.symbols = self.load_symbols()

    @abstractmethod
    def load_symbols(self) -> List[str]:
        pass

    @abstractmethod
    def fetch_symbol_data(self, symbol: str, start_date: str, end_date: str, interval='1 hour') -> pd.DataFrame:
        pass

    def load_data(self, start_date: str, end_date: str, intervals=None) -> Dict[str, pd.DataFrame]:
        if intervals is None:
            intervals = {symbol: TIMEFRAMES[0] for symbol in self.symbols}
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_symbol = {executor.submit(self.fetch_symbol_data, symbol, start_date, end_date, intervals[symbol]): symbol for symbol in self.symbols}
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    results[symbol] = future.result()
                    logger.info(f"Successfully loaded data for {symbol}")
                except Exception as e:
                    logger.error(f"Error loading data for {symbol}: {str(e)}")
                    results[symbol] = None
        return results

class IBBaseLoader(BaseDataLoader):
    def __init__(self, max_workers=16, contract_type='STOCK'):
        self.contract_type = contract_type.upper()
        super().__init__(max_workers)
        self.ib = IB()
        self.connect_lock = asyncio.Lock()
        # No need to create a separate loop here

    def load_symbols(self) -> List[str]:
        file_path = MARKET_ASSET_TYPES.get(self.contract_type, '')
        if not file_path:
            raise ValueError(f"No symbol file found for contract type: {self.contract_type}")
        with open(file_path, 'r') as f:
            return [symbol.strip() for symbol in f.read().strip().split(',')]

    def create_contract(self, symbol: str) -> Contract:
        if self.contract_type == 'STOCK':
            return Stock(symbol, 'SMART', 'USD')
        elif self.contract_type == 'OPTION':
            return Option(symbol, '20241026', 150, 'C', 'SMART')
        elif self.contract_type == 'FUTURE':
            return Future(symbol, '202412', 'GLOBEX')
        elif self.contract_type == 'INDEX':
            return Index(symbol, 'SMART', 'USD')
        elif self.contract_type == 'FOREX':
            return Forex(symbol)
        elif self.contract_type == 'CFD':
            return CFD(symbol, 'SMART', 'USD')
        elif self.contract_type == 'COMMODITY':
            return Commodity(symbol, 'SMART', 'USD')
        elif self.contract_type == 'BOND':
            return Bond(secIdType='ISIN', secId='US03076KAA60')
        else:
            raise ValueError(f"Unsupported contract type: {self.contract_type}")

    async def ensure_connected(self):
        async with self.connect_lock:
            if not self.ib.isConnected():
                try:
                    await asyncio.wait_for(
                        self.ib.connectAsync(SOCKET['HOST'], SOCKET['PORT'], clientId=random.randint(1, 9999)),
                        timeout=10
                    )
                    self.ib.reqMarketDataType(4) 
                except asyncio.TimeoutError:
                    raise ConnectionError("Connection timeout")
                except Exception as e:
                    raise ConnectionError(f"Connection failed: {str(e)}")

    async def load_ib_async_data(self, symbol, interval, end_date):
        try:
            await self.ensure_connected()

            contract = self.create_contract(symbol)

            duration_str = DURATION_MAP.get(interval, '30 D')
            end_datetime = datetime.datetime.strptime(end_date, "%Y%m%d")
            formatted_end_date = end_datetime.strftime("%Y%m%d %H:%M:%S")

            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=formatted_end_date,
                durationStr=duration_str,
                barSizeSetting=interval,
                whatToShow='MIDPOINT',
                useRTH=True
            )

            if not bars:
                logger.warning(f"No data found for {symbol} with interval {interval}")
                return pd.DataFrame()

            df = util.df(bars)
            df.set_index('date', inplace=True)
            df.index = pd.to_datetime(df.index)
            df = df[['open', 'high', 'low', 'close', 'volume']]
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

            df['Volume'] = df['Volume'].replace(-1, float('nan'))
            print(df.head())  # Print the head of the DataFrame
            return df.sort_index()

        except Exception as e:
            logger.error(f"Failed to fetch data from IB for {symbol}: {str(e)}")
            return pd.DataFrame()

    def fetch_symbol_data(self, symbol, start_date, end_date, interval=TIMEFRAMES[0]):
        # Use asyncio.run within the thread
        return asyncio.run(self.load_ib_async_data(symbol, interval, end_date))

    async def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()


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

    def fetch_symbol_data(self, symbol: str, start_date: str, end_date: str, interval=TIMEFRAMES[0]) -> pd.DataFrame:
        try:
            if symbol.endswith('USD') and symbol != 'USDT':
                symbol = symbol[:-3] + 'USDT'

            start_ts = int(datetime.datetime.strptime(start_date, "%Y%m%d").replace(tzinfo=pytz.UTC).timestamp() * 1000)
            end_ts = int(datetime.datetime.strptime(end_date, "%Y%m%d").replace(tzinfo=pytz.UTC).timestamp() * 1000)

            klines = self.client.get_historical_klines(
                symbol, 
                BinanceClient.KLINE_INTERVAL_1DAY, 
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
            print(df.head())  # Print the head of the DataFrame
            return df
        except Exception as e:
            logger.error(f"Failed to fetch data from Binance for {symbol}: {str(e)}")
            raise

def get_data_loader(asset_type: str) -> BaseDataLoader:
    asset_type = asset_type.upper()
    
    if asset_type in MARKET_ASSET_TYPES:
        if asset_type == 'CRYPTO':
            return BinanceCryptoLoader()
        else:
            return IBBaseLoader(contract_type=asset_type)
    else:
        raise ValueError(f"Unsupported asset type: {asset_type}")

async def main(): 
    loader = None
    try:
        loader = get_data_loader('STOCK')
        data = loader.load_data('20230101', '20230930')
        
        success_count = 0
        no_data_count = 0
        failure_count = 0
        
        for symbol, df in data.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                print(f"{symbol}: {len(df)} rows") 
                success_count += 1
            elif df is None:
                print(f"{symbol}: Failed to retrieve data")
                failure_count += 1
            else:
                print(f"{symbol}: No data available")
                no_data_count += 1
        
        print(f"\nSummary:")
        print(f"Successful data retrievals: {success_count}")
        print(f"Symbols with no data: {no_data_count}")
        print(f"Failed data retrievals: {failure_count}")
        
        if no_data_count > 0 or failure_count > 0:
            print("\nPossible reasons for no data or failures:")
            print("1. The specified date range might not have data for some symbols")
            print("2. Connection issues with Interactive Brokers")
            print("3. Insufficient permissions for certain symbols")
            print("4. Symbol not recognized or no longer active")
    except Exception as e:
        print(f"An error occurred while running the script: {str(e)}")
    finally:
        if loader and isinstance(loader, IBBaseLoader):
            await loader.disconnect()
        print("Script execution completed.")

if __name__ == "__main__":
    asyncio.run(main())