import logging
import pandas as pd
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import pyqtSignal, QSize
from lightweight_charts.widgets import QtChart
from config import TIMEFRAMES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LightweightChart(QWidget):
    timeframe_changed = pyqtSignal(str, str)  # Signal will emit (new_timeframe, symbol)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Initialize chart
        self.chart = QtChart(toolbox=True)
        self.chart.legend(True)
        self.chart.topbar.textbox('symbol', '')
        
        # State tracking
        self.current_timeframe = TIMEFRAMES[3]  # Default to '1 hour'
        self.current_symbol = None
        self.last_loaded_timeframe = None
        self.timeframe_state = {tf: False for tf in TIMEFRAMES}  # Track loaded state for each timeframe
        
        # Initialize chart components
        self.init_timeframe_switcher()
        self.init_moving_averages()
        
        # Add webview to layout
        self.webview = self.chart.get_webview()
        if self.webview:
            self.webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.webview.setMinimumSize(QSize(800, 600))
        self.layout.addWidget(self.webview)
        
        logger.info("LightweightChart initialized")

    def init_timeframe_switcher(self):
        """Initialize timeframe switcher with state management."""
        try:
            def handle_timeframe_change(chart):
                try:
                    tf_value = self.chart.topbar['timeframe'].value
                    for tf in TIMEFRAMES:
                        if tf.replace(' ', '') == tf_value:
                            if tf != self.current_timeframe:
                                old_tf = self.current_timeframe
                                self.current_timeframe = tf
                                logger.info(f"Timeframe changed from {old_tf} to {tf}")
                                
                                # Reset state for new timeframe
                                self.timeframe_state[tf] = False
                                
                                # Emit signal with current symbol for data reload
                                if self.current_symbol:
                                    logger.info(f"Emitting timeframe change signal: {tf}, {self.current_symbol}")
                                    self.timeframe_changed.emit(tf, self.current_symbol)
                            break
                except Exception as e:
                    logger.error(f"Error in timeframe handler: {str(e)}")

            # Set up timeframe switcher
            self.chart.topbar.switcher(
                'timeframe', 
                [tf.replace(' ', '') for tf in TIMEFRAMES],
                default=self.current_timeframe.replace(' ', ''),
                func=handle_timeframe_change
            )
            logger.info("Timeframe switcher initialized")
        except Exception as e:
            logger.error(f"Error initializing timeframe switcher: {str(e)}")

    def init_moving_averages(self):
        """Initialize moving average lines."""
        try:
            self.ma20_line = self.chart.create_line(
                'MA20',
                color='#00FF00',
                width=1,
                price_label=True,
                price_line=False
            )
            self.ma200_line = self.chart.create_line(
                'MA200',
                color='#FF0000',
                width=1,
                price_label=True,
                price_line=False
            )
            logger.info("Moving average lines initialized")
        except Exception as e:
            logger.error(f"Error initializing MA lines: {str(e)}")
            self.ma20_line = self.ma200_line = None

    def update_data(self, df, symbol, timeframe):
        """Update chart data with new timeframe data."""
        try:
            if df is None or df.empty:
                logger.warning(f"Received empty data for {symbol} at {timeframe}")
                return

            # Store current data and symbol
            self.current_symbol = symbol
            
            # Prepare data
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # Calculate moving averages
            df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
            df['MA200'] = df['Close'].rolling(window=200, min_periods=1).mean()
            
            # Update symbol display
            self.chart.topbar['symbol'].set(symbol)
            
            # Set main chart data
            self.chart.set(df)
            logger.info(f"Updated chart with {len(df)} bars for {symbol} at {timeframe}")
            
            # Update MA lines
            if hasattr(self, 'ma20_line') and hasattr(self, 'ma200_line'):
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
                    logger.info(f"Updated MA20 with {len(ma20_data)} points")
                
                if not ma200_data.empty:
                    self.ma200_line.set(ma200_data)
                    logger.info(f"Updated MA200 with {len(ma200_data)} points")
            
            # Update state
            self.timeframe_state[timeframe] = True
            self.last_loaded_timeframe = timeframe
            
            # Ensure view updates
            if self.webview:
                self.webview.update()
                
            logger.info(f"Successfully updated chart for {symbol} at {timeframe}")
        except Exception as e:
            logger.error(f"Error updating chart data: {str(e)}")

    def clear_data(self):
        """Clear all chart data."""
        try:
            # Create empty DataFrame
            empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
            empty_df.index.name = 'time'
            
            # Clear main chart
            self.chart.set(empty_df)
            
            # Clear MA lines
            if hasattr(self, 'ma20_line'):
                self.ma20_line.set(pd.DataFrame({'time': [], 'MA20': []}))
            if hasattr(self, 'ma200_line'):
                self.ma200_line.set(pd.DataFrame({'time': [], 'MA200': []}))
            
            # Reset state
            self.current_symbol = None
            self.last_loaded_timeframe = None
            self.timeframe_state = {tf: False for tf in TIMEFRAMES}
            
            # Update view
            if self.webview:
                self.webview.update()
                
            logger.info("Chart data cleared")
        except Exception as e:
            logger.error(f"Error clearing chart data: {str(e)}")

    def reset_state(self):
        """Reset chart state for new data loading."""
        try:
            self.clear_data()
            self.init_moving_averages()
            logger.info("Chart state reset")
        except Exception as e:
            logger.error(f"Error resetting chart state: {str(e)}")

    def set(self, df, symbol):
        """Set initial chart data."""
        self.update_data(df, symbol, self.current_timeframe)

    def check_timeframe_loaded(self, timeframe):
        """Check if data for a specific timeframe is loaded."""
        return self.timeframe_state.get(timeframe, False)

    def get_current_state(self):
        """Get current chart state."""
        return {
            'symbol': self.current_symbol,
            'timeframe': self.current_timeframe,
            'last_loaded': self.last_loaded_timeframe,
            'states': self.timeframe_state.copy()
        }

    def sizeHint(self):
        """Default size hint."""
        return QSize(800, 600)