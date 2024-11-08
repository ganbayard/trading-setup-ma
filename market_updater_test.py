import subprocess
import sys
from datetime import datetime

def run_updater(asset_type=None, symbols=None, timeframes=None, days_back=None):
    """Run the market updater with specified parameters."""
    command = [sys.executable, 'market_updater.py']
    
    if asset_type:
        command.extend(['--asset-type', asset_type])
    
    if symbols:
        command.extend(['--symbols'] + symbols)
    
    if timeframes:
        command.extend(['--timeframes'] + timeframes)
    
    if days_back:
        command.extend(['--days-back', str(days_back)])
    
    print(f"\nExecuting command: {' '.join(command)}")
    subprocess.run(command)

def main():
    """Test different scenarios for market data updates."""
    
    print("\n=== Testing Market Updater ===")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Start Time: {current_time}\n")

    # Test Case 1: Update crypto data with default duration from DURATION_MAP
    print("\n1. Updating crypto data with default duration (maintains exact length from DURATION_MAP)")
    run_updater(
        asset_type='CRYPTO',
        symbols=['BTCUSDT'],
        timeframes=['1 hour']  # Will maintain 60 days of data per DURATION_MAP
    )

    # Test Case 2: Update forex data with multiple timeframes (different durations)
    print("\n2. Updating forex data with multiple timeframes (different durations)")
    run_updater(
        asset_type='FOREX',
        symbols=['EURUSD'],
        timeframes=['1 hour', '4 hours']  # Will maintain 60 days and 250 days respectively
    )

    # Test Case 3: Update stock data with custom duration
    print("\n3. Updating stock data with custom duration (overrides DURATION_MAP)")
    run_updater(
        asset_type='STOCK',
        symbols=['AAPL'],
        timeframes=['1 day'],
        days_back=30  # Override default duration of 4 years
    )

    # Test Case 4: Update all crypto symbols with specific timeframe
    print("\n4. Updating all crypto symbols with specific timeframe")
    run_updater(
        asset_type='CRYPTO',
        timeframes=['4 hours']  # Will maintain 250 days per DURATION_MAP
    )

    # Test Case 5: Update multiple asset types
    print("\n5. Updating multiple asset types with specific timeframe")
    run_updater(
        asset_type='ALL',
        timeframes=['1 day']  # Will maintain duration per DURATION_MAP for each asset type
    )

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nEnd Time: {current_time}")
    print("\n=== Testing Complete ===")

if __name__ == "__main__":
    main()
