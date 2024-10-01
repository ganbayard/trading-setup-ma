import random
import logging
import pandas as pd
import mplfinance as mpf
from datetime import timedelta

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from lightweight_charts.widgets import QtChart

import asyncio
from ib_async import *
import concurrent.futures


from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout

from config import SOCKET

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LightweightChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)

        # Create chart
        self.chart_widget = QWidget()
        self.chart_layout = QHBoxLayout(self.chart_widget)
        self.chart = QtChart(self.chart_widget, toolbox=True)
        self.chart_layout.addWidget(self.chart.get_webview())
        
        # Add chart to main layout
        self.main_layout.addWidget(self.chart_widget)

    def set(self, df, symbol):
        try:
            if df is None or df.empty:
                logger.error(f"DataFrame is None or empty for {symbol}")
                return
            self.chart.set(df)
            logger.info(f"Chart set successfully for {symbol}")
        except Exception as e:
            logger.error(f"Error in LightweightChart.set for {symbol}: {str(e)}")

    def get_webview(self):
        return self

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
    



