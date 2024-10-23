# chart_types.py
import logging
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from lightweight_charts.widgets import QtChart

from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal, Qt

from config import TIMEFRAMES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LightweightChart(QWidget):
    timeframe_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Setup layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Initialize chart
        self.chart = QtChart(toolbox=True)
        self.chart.legend(True)
        self.chart.topbar.textbox('symbol', '')
        
        # Convert timeframes for chart display
        self.chart_timeframes = [tf.replace(' ', '') for tf in TIMEFRAMES]
        self.current_timeframe = TIMEFRAMES[3]  # Default to '1 hour'
        
        # Store references to chart components
        self.candlestick_series = None
        self.ma20_line = None
        self.ma200_line = None
        
        # Initialize chart components
        self.init_timeframe_switcher()
        self.init_moving_averages()
        
        # Add webview to layout
        webview = self.chart.get_webview()
        self.layout.addWidget(webview)
        
        logger.info("LightweightChart initialized")

    def init_timeframe_switcher(self):
        """Initialize the timeframe switcher with better error handling."""
        try:
            def handle_timeframe_change(chart):
                try:
                    tf_value = self.chart.topbar['timeframe'].value
                    for tf in TIMEFRAMES:
                        if tf.replace(' ', '') == tf_value:
                            if tf != self.current_timeframe:
                                self.current_timeframe = tf
                                logger.info(f"Timeframe changed to: {tf}")
                                # Clean up before emitting signal
                                self.clean_chart_data()
                                self.timeframe_changed.emit(tf)
                            break
                except Exception as e:
                    logger.error(f"Error in timeframe handler: {str(e)}")

            # Set up timeframe switcher
            self.chart.topbar.switcher('timeframe', self.chart_timeframes, default=self.chart_timeframes[3])
            self.chart.topbar['timeframe'].func = handle_timeframe_change
            logger.info("Timeframe switcher initialized")
        except Exception as e:
            logger.error(f"Error initializing timeframe switcher: {str(e)}")

    def init_moving_averages(self):
        """Initialize moving average lines with error handling."""
        try:
            self.ma20_line = self.chart.create_line('MA20', color='#00FF00', width=1, price_label=True, price_line=False)
            self.ma200_line = self.chart.create_line('MA200', color='#FF0000', width=1, price_label=True, price_line=False)
            logger.info("Moving average lines initialized")
        except Exception as e:
            logger.error(f"Error initializing MA lines: {str(e)}")
            self.ma20_line = None
            self.ma200_line = None

    def clean_chart_data(self):
        """Clean up chart data before updates."""
        try:
            if hasattr(self, 'chart'):
                if self.ma20_line:
                    self.ma20_line.clear()
                if self.ma200_line:
                    self.ma200_line.clear()
            logger.info("Chart data cleaned")
        except Exception as e:
            logger.error(f"Error cleaning chart data: {str(e)}")

    def prepare_dataframe(self, df):
        """Prepare DataFrame with data cleaning."""
        try:
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # Clean numeric columns
            numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Fill NaN values
            df['Volume'] = df['Volume'].fillna(0)
            df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].fillna(method='ffill')
            
            return self.calculate_moving_averages(df)
        except Exception as e:
            logger.error(f"Error preparing DataFrame: {str(e)}")
            return df

    def calculate_moving_averages(self, df):
        """Calculate moving averages with error handling."""
        try:
            df = df.copy()
            df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
            df['MA200'] = df['Close'].rolling(window=200, min_periods=1).mean()
            return df
        except Exception as e:
            logger.error(f"Error calculating moving averages: {str(e)}")
            return df

    def set(self, df, symbol):
        """Set chart data with improved error handling."""
        logger.info(f"Setting chart for symbol: {symbol}")
        if df is None or df.empty:
            logger.error(f"DataFrame is None or empty for {symbol}")
            return

        try:
            # Clean existing data
            self.clean_chart_data()
            
            # Update symbol display
            self.chart.topbar['symbol'].set(symbol)
            
            # Clean and prepare DataFrame
            df = self.prepare_dataframe(df)
            
            # Set candlestick data
            self.chart.set(df)
            logger.info(f"Main chart data set with {len(df)} points")

            # Update MA lines
            if not df.empty and self.ma20_line and self.ma200_line:
                ma20_data = pd.DataFrame({
                    'time': df.index,
                    'MA20': df['MA20']
                }).dropna()

                ma200_data = pd.DataFrame({
                    'time': df.index,
                    'MA200': df['MA200']
                }).dropna()

                if not ma20_data.empty:
                    self.ma20_line.set(ma20_data)
                    logger.info(f"MA20 line updated with {len(ma20_data)} points")
                
                if not ma200_data.empty:
                    self.ma200_line.set(ma200_data)
                    logger.info(f"MA200 line updated with {len(ma200_data)} points")

            # Ensure chart updates
            webview = self.chart.get_webview()
            if webview:
                webview.update()
                logger.info(f"Chart update called for {symbol}")
            
        except Exception as e:
            logger.error(f"Error setting chart for {symbol}: {str(e)}")

    def get_webview(self):
        """Return the chart's webview with error handling."""
        try:
            return self.chart.get_webview()
        except Exception as e:
            logger.error(f"Error getting webview: {str(e)}")
            return None

    def setMinimumSize(self, width, height):
        """Set minimum size for the chart widget with error handling."""
        try:
            super().setMinimumSize(width, height)
            webview = self.get_webview()
            if webview:
                webview.setMinimumSize(width, height)
        except Exception as e:
            logger.error(f"Error setting minimum size: {str(e)}")