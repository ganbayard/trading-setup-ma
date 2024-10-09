import logging
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTableView, QSplitter, QStatusBar, 
                             QProgressBar, QComboBox, QHeaderView, QMessageBox,
                             QDesktopWidget, QLineEdit, QLabel, QAbstractItemView)
from PyQt5.QtCore import Qt, QSortFilterProxyModel, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QStandardItemModel, QStandardItem

from chart_types import LightweightChart, NativeChart
from config import MARKET_ASSET_TYPES, TIMEFRAMES
from data_sources import get_data_loader

logger = logging.getLogger(__name__)

class DataLoaderThread(QThread):
    data_loaded = pyqtSignal(dict)
    progress_updated = pyqtSignal(str, int, int)
    error_occurred = pyqtSignal(str)

    def __init__(self, loader, symbols, start_date, end_date, interval='1 hour'):
        super().__init__()
        self.loader = loader
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.interval = interval
        print(f"DataLoaderThread initialized with interval: {self.interval}")

    def run(self):
        try:
            self.progress_updated.emit("Loading data...", 0, 0)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(self.loader.load_data(self.start_date, self.end_date, self.symbols, self.interval))
            self.data_loaded.emit(results)
            self.progress_updated.emit("Data loaded", 0, 100)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            loop.close()

class UIUpdater(QObject):
    update_progress = pyqtSignal(str, int, int)
    update_chart = pyqtSignal(object, str)

class MainWindow(QMainWindow):
    def __init__(self, data_loader, chart_type):
        super().__init__()
        self.setWindowTitle("Market Asset Viewer")
        self.resize(1600, 900)
        self.center_on_screen()
        self.data_loader = data_loader
        self.chart_type = chart_type
        self.chart = self.chart_type(self)
        self.current_timeframe = TIMEFRAMES[3]  # Default to '1 hour'
        if isinstance(self.chart, LightweightChart):
            self.chart.timeframe_changed.connect(self.on_timeframe_changed)
            self.current_timeframe = self.chart.current_timeframe  # Sync with chart's default
        self.assets = {}
        self.current_symbol = None
        self.latest_bar_date = None
        self.data_loader_thread = None
        self.ui_updater = UIUpdater()
        self.ui_updater.update_progress.connect(self.update_progress_bar)
        self.ui_updater.update_chart.connect(self.update_chart_safely)
        self.setup_ui()
        self.load_symbols()
        self.load_data()

    def setup_ui(self):
        self.setWindowTitle("Trading Setup MA Strategy")
        self.resize(1600, 900)

        # Main widget and layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Create a splitter for the two main columns
        splitter = QSplitter(Qt.Horizontal)

        # Column 1: Asset selector and table view
        column1_widget = QWidget()
        column1_layout = QVBoxLayout(column1_widget)
        column1_layout.setContentsMargins(10, 10, 10, 10)

        # Asset selector
        asset_selector_layout = QHBoxLayout()
        asset_selector_label = QLabel("Select Market Asset Type:")
        self.asset_selector = QComboBox()
        asset_types = list(MARKET_ASSET_TYPES.keys())
        self.asset_selector.addItems([asset_type.lower() for asset_type in asset_types])
        asset_selector_layout.addWidget(asset_selector_label)
        asset_selector_layout.addWidget(self.asset_selector)
        column1_layout.addLayout(asset_selector_layout)

        # Search box
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Search...")
        self.search_box.returnPressed.connect(self.search)
        column1_layout.addWidget(self.search_box)

        # Table view
        self.table_view = QTableView()
        self.table_model = QStandardItemModel()
        headers = ["Symbol", "Last Price", "Change", "Change %", "Volume", "MA Cross Support", "MA Cross Resistance"]
        self.table_model.setHorizontalHeaderLabels(headers)
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.doubleClicked.connect(self.on_table_double_click)
        self.table_view.clicked.connect(self.on_table_click)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        column1_layout.addWidget(self.table_view)

        # Column 2: Chart
        column2_widget = QWidget()
        column2_layout = QVBoxLayout(column2_widget)
        column2_layout.setContentsMargins(10, 10, 10, 10)

        self.chart = self.chart_type(self)
        self.chart.setMinimumSize(400, 300)
        column2_layout.addWidget(self.chart)

        # Add columns to splitter
        splitter.addWidget(column1_widget)
        splitter.addWidget(column2_widget)
        splitter.setSizes([400, 1200])

        # Add splitter to main layout
        self.main_layout.addWidget(splitter)

        # Set up asset selector connections
        self.asset_selector.setCurrentIndex(0)
        self.asset_selector.currentTextChanged.connect(self.on_asset_changed)

        # Status bar and progress bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("Loading... %p%")
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # If using LightweightChart, connect the timeframe change signal
        if isinstance(self.chart, LightweightChart):
            self.chart.timeframe_changed.connect(self.on_timeframe_changed)
            self.current_timeframe = self.chart.current_timeframe

        # Center the window on the screen
        self.center_on_screen()

    def load_symbols(self):
        self.symbols_by_asset = {}
        for asset_type, file_name in MARKET_ASSET_TYPES.items():
            file_path = file_name
            self.symbols_by_asset[asset_type.lower()] = self.load_symbols_from_file(file_path)

    def load_symbols_from_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
                symbols = [symbol.strip() for symbol in content.split(',') if symbol.strip()]
            return symbols
        except IOError:
            logger.error(f"Unable to read symbol file: {file_path}")
            return []

    def on_asset_changed(self, asset_type):
        try:
            self.data_loader = get_data_loader(asset_type.upper())
            symbols = self.symbols_by_asset.get(asset_type.lower(), [])
            self.update_table(symbols)
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to change asset type: {str(e)}")
            logger.error(f"Error changing asset type: {str(e)}")

    def update_table(self, symbols):
        self.table_model.clear()
        headers = ["Symbol", "Last Price", "Change", "Change %", "Volume", "MA Cross Support", "MA Cross Resistance", "Liquidity Status"]
        self.table_model.setHorizontalHeaderLabels(headers)
        for symbol in symbols:
            row_items = [QStandardItem(symbol)]
            for _ in range(len(headers) - 1):
                row_items.append(QStandardItem(''))
            self.table_model.appendRow(row_items)
        self.table_view.setColumnHidden(0, False)
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def on_table_click(self, index):
        symbol = self.proxy_model.data(self.proxy_model.index(index.row(), 0))
        self.current_symbol = symbol

    def on_table_double_click(self, index):
        symbol = self.proxy_model.data(self.proxy_model.index(index.row(), 0))
        self.act_on_row(symbol)

    def act_on_row(self, symbol):
        self.current_symbol = symbol
        if symbol in self.assets:
            df = self.assets[symbol]
            if isinstance(df, pd.DataFrame) and not df.empty:
                self.update_chart_safely(df, symbol)
            else:
                logger.warning(f"No data available for {symbol}")
                self.show_error_message(f"No data available for {symbol}")
        else:
            logger.warning(f"Symbol {symbol} not found in loaded data")
            self.show_error_message(f"Data for {symbol} not loaded. Please try reloading the data.")

    def load_data(self):
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=65)).strftime("%Y%m%d")  # Load 1 year of data

        if self.data_loader_thread and self.data_loader_thread.isRunning():
            self.data_loader_thread.terminate()
            self.data_loader_thread.wait()

        self.data_loader_thread = DataLoaderThread(
            self.data_loader,
            self.data_loader.symbols,
            start_date,
            end_date,
        )
        self.data_loader_thread.data_loaded.connect(self.on_data_loaded)
        self.data_loader_thread.progress_updated.connect(self.update_progress_bar)
        self.data_loader_thread.error_occurred.connect(self.on_data_load_error)
        self.data_loader_thread.start()

    def on_data_loaded(self, data):
        self.assets = data
        self.update_table_with_data(data)
        self.update_progress_bar("Data loaded", 0, 100)

    def on_data_load_error(self, error_message):
        QMessageBox.critical(self, "Error", f"Failed to load data: {error_message}")
        self.update_progress_bar("Data load failed", 0, 100)

    def calculate_ma(self, df):
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        return df
    
    def update_table_with_data(self, data=None):
        if data is None:
            data = self.assets
        is_crypto = self.asset_selector.currentText().lower() == 'crypto'
        decimal_places = 8 if is_crypto else 2

        for row in range(self.table_model.rowCount()):
            symbol = self.table_model.item(row, 0).text()
            if symbol in data:
                df = data[symbol]
                if isinstance(df, pd.DataFrame) and not df.empty:
                    # Calculate MA20 and MA200
                    df = self.calculate_ma(df)

                    last_close = df['Close'].iloc[-1]
                    prev_close = df['Close'].iloc[-2] if len(df) > 1 else last_close
                    change = last_close - prev_close
                    change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
                    volume = df['Volume'].iloc[-1]

                    # Find latest MA cross points for both support and resistance
                    ma_cross_support, ma_cross_resistance = self.find_ma_cross_points(df)

                    self.table_model.setItem(row, 1, QStandardItem(f"{last_close:.{decimal_places}f}"))
                    self.table_model.setItem(row, 2, QStandardItem(f"{change:.{decimal_places}f}"))
                    self.table_model.setItem(row, 3, QStandardItem(f"{change_percent:.2f}%"))
                    self.table_model.setItem(row, 4, QStandardItem(f"{volume:.0f}"))
                    self.table_model.setItem(row, 5, QStandardItem(f"{ma_cross_support:.{decimal_places}f}" if ma_cross_support is not None else "N/A"))
                    self.table_model.setItem(row, 6, QStandardItem(f"{ma_cross_resistance:.{decimal_places}f}" if ma_cross_resistance is not None else "N/A"))
                else:
                    for col in range(1, 7):
                        self.table_model.setItem(row, col, QStandardItem("N/A"))


    def find_ma_cross_points(self, df):
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
        return ma_cross_support, ma_cross_resistance

    def on_timeframe_changed(self, new_timeframe):
        print(f"Timeframe changed to: {new_timeframe}")
        self.current_timeframe = new_timeframe
        if self.current_symbol:
            self.load_data_for_symbol(self.current_symbol, new_timeframe)

    def load_data_for_symbol(self, symbol, timeframe):
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")  # Load 30 days of data
        
        print(f"Loading data for {symbol} with timeframe: {timeframe}")  # Add this debug print
        
        self.data_loader_thread = DataLoaderThread(
            self.data_loader,
            [symbol],
            start_date,
            end_date,
            timeframe
        )
        self.data_loader_thread.data_loaded.connect(self.on_symbol_data_loaded)
        self.data_loader_thread.progress_updated.connect(self.update_progress_bar)
        self.data_loader_thread.error_occurred.connect(self.on_data_load_error)
        self.data_loader_thread.start()

    def on_symbol_data_loaded(self, data):
        if self.current_symbol in data:
            df = data[self.current_symbol]
            if isinstance(df, pd.DataFrame) and not df.empty:
                self.update_chart_safely(df, self.current_symbol)
                self.update_table_with_data({self.current_symbol: df})
            else:
                logger.warning(f"Empty DataFrame for symbol: {self.current_symbol}")
                self.show_error_message(f"No data available for {self.current_symbol} with the selected timeframe. Try a different timeframe or symbol.")
                self.update_table_with_data({self.current_symbol: None})
        else:
            logger.warning(f"No data available for symbol: {self.current_symbol}")
            self.show_error_message(f"Failed to load data for {self.current_symbol}. Please try again later or select a different symbol.")
            self.update_table_with_data({self.current_symbol: None})
 
    def show_error_message(self, message):
        QMessageBox.warning(self, "Data Error", message)

    def update_progress_bar(self, message, min_value, max_value):
        self.progress_bar.setFormat(message)
        self.progress_bar.setRange(min_value, max_value)
        if max_value > 0:
            self.progress_bar.setValue(max_value)

    def update_chart_safely(self, df, symbol):
        logger.info(f"Updating chart for {symbol}")
        if df is not None and not df.empty:
            try:
                df.index = pd.to_datetime(df.index)
                df = df.sort_index()
                # Calculate MA20 and MA200 here
                df = self.calculate_ma(df)
                logger.info(f"DataFrame prepared for {symbol}: {len(df)} rows")
                self.chart.set(df, symbol)
                logger.info(f"Chart update called for {symbol}")
            except Exception as e:
                logger.error(f"Error updating chart for {symbol}: {str(e)}", exc_info=True)
                self.show_error_message(f"Error updating chart for {symbol}. Please try again or select a different timeframe.")
        else:
            logger.warning(f"Cannot update chart: Empty or None DataFrame for {symbol}")
            self.show_error_message(f"No data available to update chart for {symbol}. Please try a different timeframe or symbol.")



    def search(self):
        search_term = self.search_box.text().lower()
        for row in range(self.proxy_model.rowCount()):
            if search_term in self.proxy_model.data(self.proxy_model.index(row, 0)).lower():
                self.table_view.selectRow(row)
                return
        QMessageBox.information(self, "Search Result", "No matching symbol found.")

    def center_on_screen(self):
        screen_geometry = QDesktopWidget().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def closeEvent(self, event):
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if self.table_view.hasFocus():
            current_index = self.table_view.currentIndex()
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.act_on_row(self.current_symbol)
            elif event.key() == Qt.Key_Up:
                new_index = self.proxy_model.index(max(0, current_index.row() - 1), 0)
                self.table_view.setCurrentIndex(new_index)
                self.on_table_click(new_index)
            elif event.key() == Qt.Key_Down:
                new_index = self.proxy_model.index(min(self.proxy_model.rowCount() - 1, current_index.row() + 1), 0)
                self.table_view.setCurrentIndex(new_index)
                self.on_table_click(new_index)
        super().keyPressEvent(event)