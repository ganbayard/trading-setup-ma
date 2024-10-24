import logging
import threading
import pandas as pd
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QTableView, QSplitter, QStatusBar, 
                           QProgressBar, QComboBox, QHeaderView, QMessageBox,
                           QDesktopWidget, QLineEdit, QLabel, QAbstractItemView)
from PyQt5.QtCore import Qt, QSortFilterProxyModel, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from chart_types import LightweightChart
from config import MARKET_ASSET_TYPES, TIMEFRAMES
from models.market_models import (
    CryptoMTFBar, StockMTFBar, ForexMTFBar, CommodityMTFBar,
    IndexMTFBar, FutureMTFBar, OptionMTFBar, CFDMTFBar, BondMTFBar,
    TimeframeType
)

logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///market_assets.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Map asset types to their corresponding model classes
ASSET_MODEL_MAP = {
    'CRYPTO': CryptoMTFBar,
    'STOCK': StockMTFBar,
    'FOREX': ForexMTFBar,
    'COMMODITY': CommodityMTFBar,
    'INDEX': IndexMTFBar,
    'FUTURE': FutureMTFBar,
    'OPTION': OptionMTFBar,
    'CFD': CFDMTFBar,
    'BOND': BondMTFBar
}


class DataLoaderThread(QThread):
    data_loaded = pyqtSignal(dict)
    progress_updated = pyqtSignal(str, int, int)
    error_occurred = pyqtSignal(str)

    def __init__(self, asset_type, symbols=None, interval='1 hour', days_back=60):
        super().__init__()
        self.asset_type = asset_type.upper()
        self.symbols = symbols if isinstance(symbols, list) else [symbols] if symbols else None
        self.interval = interval
        self.days_back = days_back
        self._is_running = True
        self._lock = threading.Lock()
        logger.info(f"DataLoaderThread initialized with interval: {self.interval}")

    def stop(self):
        """Safely stop the thread."""
        with self._lock:
            self._is_running = False
        self.wait()

    def get_timeframe_id(self, session, timeframe: str) -> int:
        """Get timeframe ID with error handling."""
        try:
            result = session.execute(
                select(TimeframeType.id).where(TimeframeType.name == timeframe)
            ).scalar_one_or_none()
            
            if result is None:
                raise ValueError(f"Timeframe {timeframe} not found in TimeframeType table")
            return result
        except SQLAlchemyError as e:
            logger.error(f"Database error while getting timeframe ID: {str(e)}")
            raise

    def clean_market_data(self, df):
        """Clean market data with proper error handling."""
        try:
            if df is None or df.empty:
                return df

            # Clean numeric columns
            numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Fill NaN values
            df['Volume'] = df['Volume'].fillna(0)
            df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].fillna(method='ffill')

            return df
        except Exception as e:
            logger.error(f"Error cleaning market data: {str(e)}")
            return df

    def fetch_market_data(self, session, model_class, timeframe_id: int):
        """Fetch market data with improved error handling."""
        try:
            if not self._is_running:
                return {}

            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.days_back)

            query = select(model_class).where(
                and_(
                    model_class.timeframe_type == timeframe_id,
                    model_class.timestamp.between(start_date, end_date)
                )
            )

            if self.symbols:
                query = query.where(model_class.symbol.in_(self.symbols))

            result = session.execute(query)
            rows = result.fetchall()

            if not rows:
                logger.warning(f"No data found for {self.asset_type} with timeframe {self.interval}")
                return {}

            data = {}
            for row in rows:
                if not self._is_running:
                    return {}

                row = row[0]
                symbol = row.symbol
                
                if symbol not in data:
                    data[symbol] = []
                
                # Ensure no None values
                data[symbol].append({
                    'timestamp': row.timestamp,
                    'Open': row.open if row.open is not None else 0.0,
                    'High': row.high if row.high is not None else 0.0,
                    'Low': row.low if row.low is not None else 0.0,
                    'Close': row.close if row.close is not None else 0.0,
                    'Volume': row.volume if row.volume is not None else 0.0
                })

            for symbol in data:
                if not self._is_running:
                    return {}

                df = pd.DataFrame(data[symbol])
                df.set_index('timestamp', inplace=True)
                df.sort_index(inplace=True)
                df = self.clean_market_data(df)
                data[symbol] = df

            return data

        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            raise

    def run(self):
        """Run thread with improved error handling and data cleaning."""
        session = None
        try:
            with self._lock:
                session = Session()
                self.progress_updated.emit("Loading data...", 0, 0)
                
                model_class = ASSET_MODEL_MAP.get(self.asset_type)
                if not model_class:
                    raise ValueError(f"Unsupported asset type: {self.asset_type}")

                timeframe_id = self.get_timeframe_id(session, self.interval)
                results = self.fetch_market_data(session, model_class, timeframe_id)
                
                if not self._is_running:
                    return

                if not results:
                    logger.warning(f"No data available for {self.asset_type}")
                    self.error_occurred.emit(f"No data available for {self.asset_type}. Please update the database.")
                else:
                    self.data_loaded.emit(results)
                
                self.progress_updated.emit("Data loaded", 0, 100)

        except Exception as e:
            if self._is_running:
                logger.error(f"Error in DataLoaderThread: {str(e)}")
                self.error_occurred.emit(str(e))
        finally:
            if session:
                session.close()
class UIUpdater(QObject):
    update_progress = pyqtSignal(str, int, int)
    update_chart = pyqtSignal(object, str)

class MainWindow(QMainWindow):
    def __init__(self, chart_type=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Market Asset Viewer")
        self.resize(1600, 900)
        self.center_on_screen()
        
        # Set chart type
        self.chart_type = chart_type or LightweightChart
        self.chart = self.chart_type(self)
        
        # Initialize default values
        self.current_timeframe = TIMEFRAMES[3]  # Default to '1 hour'
        if isinstance(self.chart, LightweightChart):
            self.chart.timeframe_changed.connect(self.on_timeframe_changed)
            self.current_timeframe = self.chart.current_timeframe
            
        # Initialize other attributes
        self.assets = {}
        self.current_symbol = None
        self.current_asset_type = None
        self.data_loader_thread = None
        
        # Set up UI updater
        self.ui_updater = UIUpdater()
        self.ui_updater.update_progress.connect(self.update_progress_bar)
        self.ui_updater.update_chart.connect(self.update_chart_safely)
        
        # Set up UI
        self.setup_ui()
        self.load_symbols()

        self._loading_lock = threading.Lock()
        self._chart_update_lock = threading.Lock()


    def setup_ui(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

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

        self.main_layout.addWidget(splitter)

        self.asset_selector.setCurrentIndex(0)
        self.asset_selector.currentTextChanged.connect(self.on_asset_changed)

        # Status bar and progress bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("Loading... %p%")
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.progress_bar)

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
            self.current_asset_type = asset_type.upper()
            symbols = self.symbols_by_asset.get(asset_type.lower(), [])
            self.update_table(symbols)
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to change asset type: {str(e)}")
            logger.error(f"Error changing asset type: {str(e)}")

    def update_table(self, symbols):
        self.table_model.clear()
        headers = ["Symbol", "Last Price", "Change", "Change %", "Volume", "MA Cross Support", "MA Cross Resistance"]
        self.table_model.setHorizontalHeaderLabels(headers)
        for symbol in symbols:
            row_items = [QStandardItem(symbol)]
            for _ in range(len(headers) - 1):
                row_items.append(QStandardItem(''))
            self.table_model.appendRow(row_items)

    def calculate_ma(self, df):
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        return df

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

    def update_table_with_data(self, data=None):
        """Update table with improved error handling."""
        try:
            if data is None:
                data = self.assets
            is_crypto = self.asset_selector.currentText().lower() == 'crypto'
            decimal_places = 8 if is_crypto else 2

            for row in range(self.table_model.rowCount()):
                symbol = self.table_model.item(row, 0).text()
                if symbol in data:
                    df = data[symbol]
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        df = self.calculate_ma(df)

                        last_close = df['Close'].iloc[-1]
                        prev_close = df['Close'].iloc[-2] if len(df) > 1 else last_close
                        change = last_close - prev_close
                        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
                        volume = df['Volume'].iloc[-1]

                        ma_cross_support, ma_cross_resistance = self.find_ma_cross_points(df)

                        # Set items with proper formatting and error checking
                        def set_table_item(col, value, format_str):
                            try:
                                formatted_value = format_str.format(value) if value is not None else "N/A"
                                self.table_model.setItem(row, col, QStandardItem(formatted_value))
                            except Exception as e:
                                logger.error(f"Error setting table item: {str(e)}")
                                self.table_model.setItem(row, col, QStandardItem("N/A"))

                        set_table_item(1, last_close, f"{{:.{decimal_places}f}}")
                        set_table_item(2, change, f"{{:.{decimal_places}f}}")
                        set_table_item(3, change_percent, "{:.2f}%")
                        set_table_item(4, volume, "{:.0f}")
                        set_table_item(5, ma_cross_support, f"{{:.{decimal_places}f}}")
                        set_table_item(6, ma_cross_resistance, f"{{:.{decimal_places}f}}")
                    else:
                        for col in range(1, 7):
                            self.table_model.setItem(row, col, QStandardItem("N/A"))
        except Exception as e:
            logger.error(f"Error updating table with data: {str(e)}")

    def on_table_click(self, index):
        symbol = self.proxy_model.data(self.proxy_model.index(index.row(), 0))
        self.current_symbol = symbol
        logger.info(f"Selected symbol: {symbol}")

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
        """Load data for current asset type."""
        try:
            if self.data_loader_thread and self.data_loader_thread.isRunning():
                self.data_loader_thread.stop()
                self.data_loader_thread.wait()
                self.data_loader_thread.deleteLater()

            self.data_loader_thread = DataLoaderThread(
                asset_type=self.current_asset_type,
                interval=self.current_timeframe
            )
            self.data_loader_thread.data_loaded.connect(self.on_data_loaded)
            self.data_loader_thread.progress_updated.connect(self.update_progress_bar)
            self.data_loader_thread.error_occurred.connect(self.on_data_load_error)
            self.data_loader_thread.start()
        except Exception as e:
            logger.error(f"Error in load_data: {str(e)}")
            self.show_error_message(f"Failed to load data: {str(e)}")

    def load_data_for_symbol(self, symbol, timeframe):
        """Load data for a specific symbol and timeframe with improved synchronization."""
        try:
            with self._loading_lock:
                # Reset chart before loading new data
                with self._chart_update_lock:
                    if hasattr(self, 'chart') and self.chart:
                        self.chart.reset_chart()
                
                # Clean up existing thread if running
                if self.data_loader_thread and self.data_loader_thread.isRunning():
                    self.data_loader_thread.stop()
                    self.data_loader_thread.wait()
                    self.data_loader_thread.deleteLater()

                # Create and start new thread
                self.data_loader_thread = DataLoaderThread(
                    asset_type=self.current_asset_type,
                    symbols=symbol,
                    interval=timeframe
                )
                
                # Connect signals
                self.data_loader_thread.data_loaded.connect(self.on_symbol_data_loaded)
                self.data_loader_thread.progress_updated.connect(self.update_progress_bar)
                self.data_loader_thread.error_occurred.connect(self.on_data_load_error)
                
                self.data_loader_thread.start()
                
        except Exception as e:
            logger.error(f"Error in load_data_for_symbol: {str(e)}")
            self.show_error_message(f"Failed to load symbol data: {str(e)}")


    def on_data_load_finished(self):
        """Handle completion of data loading."""
        try:
            with self._loading_lock:
                if self.data_loader_thread:
                    self.data_loader_thread.deleteLater()
                    self.data_loader_thread = None
                self.update_progress_bar("Data load complete", 0, 100)
        except Exception as e:
            logger.error(f"Error in on_data_load_finished: {str(e)}")


    def on_data_loaded(self, data):
        """Handle loaded data with improved error handling."""
        try:
            self.assets = data
            self.update_table_with_data(data)
            self.update_progress_bar("Data loaded", 0, 100)
            logger.info("Data loaded and table updated")
        except Exception as e:
            logger.error(f"Error handling loaded data: {str(e)}")
            self.show_error_message("Failed to process loaded data")


    def on_symbol_data_loaded(self, data):
        """Handle loaded symbol data with improved error handling."""
        try:
            with self._loading_lock:
                if self.current_symbol in data:
                    df = data[self.current_symbol]
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        # Update chart first
                        self.update_chart_safely(df, self.current_symbol)
                        # Then update table
                        self.update_table_with_data({self.current_symbol: df})
                    else:
                        logger.warning(f"Empty DataFrame for symbol: {self.current_symbol}")
                        self.show_error_message(
                            f"No data available for {self.current_symbol} with the selected timeframe. "
                            "Try a different timeframe or symbol."
                        )
                        self.update_table_with_data({self.current_symbol: None})
                else:
                    logger.warning(f"No data available for symbol: {self.current_symbol}")
                    self.show_error_message(
                        f"Failed to load data for {self.current_symbol}. "
                        "Please try again later or select a different symbol."
                    )
                    self.update_table_with_data({self.current_symbol: None})
        except Exception as e:
            logger.error(f"Error processing loaded symbol data: {str(e)}")
            self.show_error_message("Error processing loaded data")
    def on_data_load_error(self, error_message):
        QMessageBox.critical(self, "Error", f"Failed to load data: {error_message}")
        self.update_progress_bar("Data load failed", 0, 100)
        logger.error(f"Data load error: {error_message}")

    def show_error_message(self, message):
        QMessageBox.warning(self, "Data Error", message)
        logger.warning(f"Error message shown: {message}")

    def update_progress_bar(self, message, min_value, max_value):
        self.progress_bar.setFormat(message)
        self.progress_bar.setRange(min_value, max_value)
        if max_value > 0:
            self.progress_bar.setValue(max_value)

    def update_chart_safely(self, df, symbol):
        """Update chart with improved synchronization and error handling."""
        logger.info(f"Updating chart for {symbol}")
        if df is not None and not df.empty:
            try:
                df.index = pd.to_datetime(df.index)
                df = df.sort_index()
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

    def on_timeframe_changed(self, new_timeframe):
        """Handle timeframe changes with improved synchronization and validation."""
        try:
            with self._loading_lock:
                logger.info(f"MainWindow received timeframe change: {new_timeframe}")
                
                # Validate timeframe change
                if new_timeframe not in TIMEFRAMES:
                    logger.error(f"Invalid timeframe received: {new_timeframe}")
                    return
                
                if new_timeframe != self.current_timeframe:
                    old_timeframe = self.current_timeframe
                    self.current_timeframe = new_timeframe
                    
                    # Clean up existing data and chart
                    self.cleanup_before_timeframe_change()
                    
                    if self.current_symbol and self.current_asset_type:
                        logger.info(f"Loading new data for {self.current_symbol} with timeframe {new_timeframe}")
                        self.load_data_for_symbol(self.current_symbol, new_timeframe)
                    else:
                        # Reload all data with new timeframe
                        self.load_data()
                        
                    logger.info(f"Timeframe changed from {old_timeframe} to {new_timeframe}")
        except Exception as e:
            logger.error(f"Error handling timeframe change in MainWindow: {str(e)}")
            self.show_error_message(f"Failed to update timeframe: {str(e)}")

    def cleanup_before_timeframe_change(self):
        """Clean up resources before timeframe change with improved synchronization."""
        try:
            with self._loading_lock:
                # Stop any running data loader thread
                if self.data_loader_thread and self.data_loader_thread.isRunning():
                    logger.info("Stopping existing data loader thread")
                    self.data_loader_thread.stop()
                    self.data_loader_thread.wait()
                    self.data_loader_thread.deleteLater()
                    self.data_loader_thread = None

                # Reset chart data
                with self._chart_update_lock:
                    if hasattr(self, 'chart') and self.chart:
                        logger.info("Resetting chart data")
                        self.chart.reset_chart()

                # Clear existing data
                self.assets = {}
                
                # Update UI to show loading state
                self.update_progress_bar("Loading new timeframe data...", 0, 0)
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")


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
        """Handle application close event with improved cleanup."""
        try:
            if self.data_loader_thread and self.data_loader_thread.isRunning():
                self.data_loader_thread.stop()
                self.data_loader_thread.wait()
                self.data_loader_thread.deleteLater()
        except Exception as e:
            logger.error(f"Error in closeEvent: {str(e)}")
        finally:
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