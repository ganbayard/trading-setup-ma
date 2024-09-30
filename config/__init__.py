import yaml
import os

abspath = os.path.dirname(os.path.abspath(__file__))
print(abspath)

with open("config/config.yml", 'r') as ymlfile:
    cfg = yaml.safe_load(ymlfile)

ENV                 = cfg['ENV']  # PROD or DEV
LOG                 = cfg[ENV]['LOG']
DB                  = cfg[ENV]['DB']
SOCKET              = cfg[ENV]['SOCKET']
NORGATE             = cfg[ENV]['NORGATE']
SYMBOLS             = cfg[ENV]['SYMBOLS']
MARKET_ASSET_TYPES  = cfg[ENV]['MARKET_ASSET_TYPES']
OPENAI              = cfg[ENV]['OPENAI']
TIMEFRAMES          = cfg['TIMEFRAMES']
DURATION_MAP        = cfg['DURATION_MAP']