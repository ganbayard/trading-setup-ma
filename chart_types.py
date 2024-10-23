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
        
        # Initialize chart components
        self.init_timeframe_switcher()
        self.init_moving_averages()
        
        # Add webview to layout
        webview = self.chart.get_webview()
        self.layout.addWidget(webview)
        
        logger.info("LightweightChart initialized")

    def init_timeframe_switcher(self):
        """Initialize the timeframe switcher."""
        try:
            # Add timeframe switcher to topbar
            self.chart.topbar.switcher('timeframe', self.chart_timeframes, default=self.chart_timeframes[3])

            # Define timeframe change handler
            def handle_timeframe_change(chart):
                try:
                    tf_value = self.chart.topbar['timeframe'].value
                    # Find corresponding original timeframe
                    for tf in TIMEFRAMES:
                        if tf.replace(' ', '') == tf_value:
                            if tf != self.current_timeframe:
                                self.current_timeframe = tf
                                logger.info(f"Timeframe changed to: {tf}")
                                self.timeframe_changed.emit(tf)
                            break
                except Exception as e:
                    logger.error(f"Error in timeframe handler: {str(e)}")

            # Set the handler
            self.chart.topbar['timeframe'].func = handle_timeframe_change
            logger.info("Timeframe switcher initialized")
        except Exception as e:
            logger.error(f"Error initializing timeframe switcher: {str(e)}")

    def init_moving_averages(self):
        """Initialize moving average lines."""
        try:
            # Create MA lines with proper names and colors
            self.ma20_line  = self.chart.create_line('MA20', color='#00FF00', width=1, price_label=True, price_line = False)
            self.ma200_line = self.chart.create_line('MA200', color='#FF0000', width=1, price_label=True, price_line = False )
            logger.info("Moving average lines initialized")
        except Exception as e:
            logger.error(f"Error initializing MA lines: {str(e)}")

    def calculate_moving_averages(self, df):
        """Calculate moving averages for the given DataFrame."""
        try:
            df = df.copy()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA200'] = df['Close'].rolling(window=200).mean()
            return df
        except Exception as e:
            logger.error(f"Error calculating moving averages: {str(e)}")
            return df

    def set(self, df, symbol):
        """Set chart data with error handling."""
        logger.info(f"Setting chart for symbol: {symbol}")
        if df is None or df.empty:
            logger.error(f"DataFrame is None or empty for {symbol}")
            return

        try:
            # Update symbol display
            self.chart.topbar['symbol'].set(symbol)
            
            # Prepare DataFrame
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            df = self.calculate_moving_averages(df)
            
            # Set candlestick data
            self.chart.set(df)
            logger.info(f"Main chart data set with {len(df)} points")

            # Update MA lines if they exist
            if hasattr(self, 'ma20_line') and hasattr(self, 'ma200_line'):
                try:
                    # Prepare MA data
                    ma20_data = pd.DataFrame({
                        'time': df.index,
                        'MA20': df['MA20']
                    }).dropna()

                    ma200_data = pd.DataFrame({
                        'time': df.index,
                        'MA200': df['MA200']
                    }).dropna()

                    # Set MA lines
                    if not ma20_data.empty:
                        self.ma20_line.set(ma20_data)
                        logger.info(f"MA20 line updated with {len(ma20_data)} points")
                    
                    if not ma200_data.empty:
                        self.ma200_line.set(ma200_data)
                        logger.info(f"MA200 line updated with {len(ma200_data)} points")

                except Exception as e:
                    logger.error(f"Error updating MA lines: {str(e)}")
            else:
                logger.warning("MA lines not initialized, skipping MA updates")

        except Exception as e:
            logger.error(f"Error setting chart for {symbol}: {str(e)}")
        finally:
            # Ensure chart updates
            try:
                self.chart.get_webview().update()
            except Exception as e:
                logger.error(f"Error updating webview: {str(e)}")

    def get_webview(self):
        """Return the chart's webview."""
        return self.chart.get_webview()

    def setMinimumSize(self, width, height):
        """Set minimum size for the chart widget."""
        super().setMinimumSize(width, height)
        webview = self.get_webview()
        if webview:
            webview.setMinimumSize(width, height)