import numpy as np

def calculate_ma_cross(df):
    if df is None or df.empty:
        return None, None

    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA200'] = df['close'].rolling(window=200).mean()
    df['cross'] = np.where(df['MA20'] > df['MA200'], 1, 0)
    df['cross_change'] = df['cross'].diff()

    last_bullish_cross = df[df['cross_change'] == 1].iloc[-1]['close'] if any(df['cross_change'] == 1) else None
    last_bearish_cross = df[df['cross_change'] == -1].iloc[-1]['close'] if any(df['cross_change'] == -1) else None

    return last_bullish_cross, last_bearish_cross