import logging
import mplfinance as mpf
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from lightweight_charts.widgets import QtChart


from ib_async import *

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import pyqtSignal, QTimer

from config import TIMEFRAMES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LightweightChart(QWidget):
    timeframe_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.chart = QtChart(toolbox=True)
        self.chart.legend(True)
        self.chart.topbar.textbox('symbol', '')
        
        chart_timeframes = [tf.replace(' ', '') for tf in TIMEFRAMES]
        self.chart.topbar.switcher('timeframe', chart_timeframes, default=chart_timeframes[3])  # Default to '1day'
        
        self.layout.addWidget(self.chart.get_webview())
        
        self.current_timeframe = TIMEFRAMES[3]  # Default to '1 day'
        
        self.chart.topbar['timeframe'].func = self.on_timeframe_changed

        # Create series for MA20 and MA200
        self.ma20_series = self.chart.create_line('MA20', color='#ff0000', width=1)
        self.ma200_series = self.chart.create_line('MA200', color='#0000ff', width=1)

        logger.info("LightweightChart initialized")

    def on_timeframe_changed(self, chart):
        new_timeframe = self.chart.topbar['timeframe'].value
        original_timeframe = next(tf for tf in TIMEFRAMES if tf.replace(' ', '') == new_timeframe)
        if original_timeframe != self.current_timeframe:
            self.current_timeframe = original_timeframe
            self.timeframe_changed.emit(original_timeframe)
        logger.info(f"Timeframe changed to {original_timeframe}")

    def calculate_ma(self, df, period):
        return df['Close'].rolling(window=period).mean()

    def set(self, df, symbol):
        logger.info(f"Setting chart for symbol: {symbol}")
        if df is None or df.empty:
            logger.error(f"DataFrame is None or empty for {symbol}")
            return
        try:
            self.chart.topbar['symbol'].set(symbol)
            
            # Ensure the index is in the correct format
            df.index = pd.to_datetime(df.index)
            
            # Calculate MA20 and MA200
            df['MA20'] = self.calculate_ma(df, 20)
            df['MA200'] = self.calculate_ma(df, 200)
            
            # Set main chart data
            self.chart.set(df)
            logger.info(f"Main chart data set with {len(df)} points")

            # Set MA20 and MA200 series
            ma20_data = df[['MA20']].reset_index()
            ma20_data.columns = ['time', 'value']
            ma200_data = df[['MA200']].reset_index()
            ma200_data.columns = ['time', 'value']

            self.ma20_series.set(ma20_data)
            self.ma200_series.set(ma200_data)
            logger.info("MA20 and MA200 data set")

            logger.info(f"Chart set successfully for {symbol}")
        except Exception as e:
            logger.error(f"Error setting chart for {symbol}: {str(e)}", exc_info=True)

    def get_webview(self):
        return self.chart.get_webview()

class NativeChart(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=8, height=4, dpi=100, max_bars=300):
        self.max_bars = max_bars
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.setContentsMargins(0, 0, 0, 0)

    def set(self, df, symbol):
        self.axes.clear()
        df_trimmed = df.tail(self.max_bars)
        
        mystyle = mpf.make_mpf_style(base_mpf_style='binance', rc={'axes.labelsize': 'small'}, gridstyle='-')
        mpf.plot(df_trimmed, type='candle', ax=self.axes, show_nontrading=False, ylabel='', 
                 style=mystyle, xrotation=15, datetime_format='%Y-%m-%d')
        self.axes.grid(True)
        self.axes.set_title(f"{symbol} Chart (Last 300 Bars)")
        self.draw()

    def get_webview(self):
        return self

def load_chart_type(chart_type):
    if chart_type == 'lightweight':
        return LightweightChart
    elif chart_type == 'nativechart':
        return NativeChart
    else:
        raise ValueError(f"Unknown chart type: {chart_type}")
    