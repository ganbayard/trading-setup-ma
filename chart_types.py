import logging
import pandas as pd
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import pyqtSignal, QSize, QTimer
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
        
        # Initialize state tracking
        self.current_timeframe = TIMEFRAMES[3]  # Default to '1 hour'
        self.current_symbol = None
        self.last_loaded_timeframe = None
        self.timeframe_state = {tf: False for tf in TIMEFRAMES}
        
        # Initialize line references
        self.ma20_line = None
        self.ma200_line = None
        self.support_line = None
        self.resistance_line = None
        
        # Initialize chart
        self.chart = QtChart(toolbox=True)
        
        # Add small delay to ensure chart is fully initialized
        QTimer.singleShot(100, self.initialize_chart_components)
        
        # Add webview to layout
        self.webview = self.chart.get_webview()
        if self.webview:
            self.webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.webview.setMinimumSize(QSize(800, 600))
        self.layout.addWidget(self.webview)
        
        logger.info("LightweightChart base initialization completed")

    def initialize_chart_components(self):
        """Initialize chart components after brief delay"""
        try:
            self.chart.legend(True)
            self.chart.topbar.textbox('symbol', '')
            self.init_timeframe_switcher()
            self.init_moving_averages()
            logger.info("Chart components initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing chart components: {str(e)}")

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
                price_line=False,
                price_label=True
            )
            self.ma200_line = self.chart.create_line(
                'MA200',
                color='#FF0000',
                width=1,
                price_line=False,
                price_label=True
            )
            logger.info("Moving average lines initialized")
        except Exception as e:
            logger.error(f"Error initializing MA lines: {str(e)}")
            self.ma20_line = self.ma200_line = None

    def _reset_chart_completely(self):
        """Complete reset of chart, removing all indicators and lines."""
        try:
            # Remove all existing lines and clear references
            if hasattr(self.chart, 'lines'):
                # Create a copy of the lines list to avoid modification during iteration
                lines = self.chart.lines.copy()
                for line in lines:
                    try:
                        # Force line removal from chart
                        self.chart.remove_line(line)
                        line.remove()
                    except Exception as e:
                        logger.error(f"Error removing line {line.name}: {str(e)}")

            # Reset all references to None
            self.ma20_line = None
            self.ma200_line = None
            self.support_line = None
            self.resistance_line = None

            # Force a chart update
            if self.webview:
                self.webview.update()

            # Reinitialize moving averages after cleanup
            self.init_moving_averages()

        except Exception as e:
            logger.error(f"Error in complete chart reset: {str(e)}")

    def _clear_all_lines(self):
        """Clear all lines from the chart."""
        try:
            if hasattr(self.chart, 'lines'):
                # Get list of existing lines
                existing_lines = []
                for line in self.chart.lines:
                    existing_lines.append(line)
                
                # Remove each line
                for line in existing_lines:
                    try:
                        self.chart.remove_line(line)
                    except Exception as e:
                        logger.error(f"Error removing line: {str(e)}")
            
            self.ma20_line = None
            self.ma200_line = None
            self.support_line = None
            self.resistance_line = None
            
            if self.webview:
                self.webview.update()
                
        except Exception as e:
            logger.error(f"Error clearing lines: {str(e)}")

    def update_data(self, df, symbol, timeframe):
        """Update chart data with new timeframe data."""
        try:
            if df is None or df.empty:
                logger.warning(f"Received empty data for {symbol} at {timeframe}")
                return

            # Clear all existing lines first
            self._clear_all_lines()

            # Store current data and symbol
            self.current_symbol = symbol

            df = df.copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # Set main chart data first
            self.chart.set(df)
            self.chart.topbar['symbol'].set(symbol)
            
            # Calculate moving averages
            df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
            df['MA200'] = df['Close'].rolling(window=200, min_periods=1).mean()

            # Create MA lines
            if not self.ma20_line:
                self.ma20_line = self.chart.create_line(
                    'MA20',
                    color='#00FF00',
                    width=1
                )

            if not self.ma200_line:
                self.ma200_line = self.chart.create_line(
                    'MA200',
                    color='#FF0000',
                    width=1
                )

            # Update MA line data
            if self.ma20_line:
                ma20_data = pd.DataFrame({
                    'time': df.index,
                    'MA20': df['MA20']
                }).dropna()
                self.ma20_line.set(ma20_data)
            
            if self.ma200_line:
                ma200_data = pd.DataFrame({
                    'time': df.index,
                    'MA200': df['MA200']
                }).dropna()
                self.ma200_line.set(ma200_data)

            # Find MA cross points
            ma_cross_support = None
            ma_cross_resistance = None
            
            for i in range(len(df) - 1, 0, -1):
                if df['MA20'].iloc[i] < df['MA200'].iloc[i] and df['MA20'].iloc[i-1] >= df['MA200'].iloc[i-1]:
                    if ma_cross_resistance is None:
                        ma_cross_resistance = max(df['MA20'].iloc[i], df['MA200'].iloc[i])
                elif df['MA20'].iloc[i] > df['MA200'].iloc[i] and df['MA20'].iloc[i-1] <= df['MA200'].iloc[i-1]:
                    if ma_cross_support is None:
                        ma_cross_support = min(df['MA20'].iloc[i], df['MA200'].iloc[i])
                
                if ma_cross_support is not None and ma_cross_resistance is not None:
                    break

            # Create and update support/resistance lines
            if ma_cross_support is not None:
                if not self.support_line:
                    self.support_line = self.chart.create_line(
                        'Support',
                        color='#00FFFF',
                        width=1
                    )
                
                if self.support_line:
                    support_data = pd.DataFrame({
                        'time': df.index,
                        'Support': [float(ma_cross_support)] * len(df.index)
                    })
                    self.support_line.set(support_data)

            if ma_cross_resistance is not None:
                if not self.resistance_line:
                    self.resistance_line = self.chart.create_line(
                        'Resistance',
                        color='#FF69B4',
                        width=1
                    )
                
                if self.resistance_line:
                    resistance_data = pd.DataFrame({
                        'time': df.index,
                        'Resistance': [float(ma_cross_resistance)] * len(df.index)
                    })
                    self.resistance_line.set(resistance_data)

            # Update state
            self.timeframe_state[timeframe] = True
            self.last_loaded_timeframe = timeframe
            
            # Force final update
            if self.webview:
                self.webview.update()
                
            logger.info(f"Successfully updated chart for {symbol} at {timeframe}")
        except Exception as e:
            logger.error(f"Error updating chart data: {str(e)}")
            self._clear_all_lines()

    def clear_data(self):
        """Clear all chart data."""
        try:
            # Clear all lines first
            self._clear_all_lines()
            
            # Create empty DataFrame
            empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
            empty_df.index.name = 'time'
            
            # Clear main chart
            self.chart.set(empty_df)
            
            # Reset state
            self.current_symbol = None
            self.last_loaded_timeframe = None
            self.timeframe_state = {tf: False for tf in TIMEFRAMES}
            
            # Force update
            if self.webview:
                self.webview.update()
                
            logger.info("Chart data cleared")
        except Exception as e:
            logger.error(f"Error clearing chart data: {str(e)}")

    def reset_state(self):
        """Reset chart state for new data loading."""
        try:
            self.clear_data()
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