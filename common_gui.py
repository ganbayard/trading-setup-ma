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


ASSET_MODEL_MAP = {
    'CRYPTO'    : CryptoMTFBar,
    'STOCK'     : StockMTFBar,
    'FOREX'     : ForexMTFBar,
    'COMMODITY' : CommodityMTFBar,
    'INDEX'     : IndexMTFBar,
    'FUTURE'    : FutureMTFBar,
    'OPTION'    : OptionMTFBar,
    'CFD'       : CFDMTFBar,
    'BOND'      : BondMTFBar
}

class NumericSortProxyModel(QSortFilterProxyModel):
    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left, Qt.UserRole)
        right_data = self.sourceModel().data(right, Qt.UserRole)

        try:
            if pd.isna(left_data):
                return False
            if pd.isna(right_data):
                return True

            if isinstance(left_data, (int, float)) and isinstance(right_data, (int, float)):
                return float(left_data) < float(right_data)

            try:
                return float(str(left_data).replace('%', '')) < float(str(right_data).replace('%', ''))
            except ValueError:
                return str(left_data) < str(right_data)
        except Exception:
            return str(left_data) < str(right_data)

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


            numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df['Volume'] = df['Volume'].fillna(0)
            df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].ffill()

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
        super().__init__()
        self.setWindowTitle("Market Asset Viewer")
        self.resize(1600, 900)
        
        # Initialize state
        self.chart_type = chart_type or LightweightChart
        self.current_timeframe = TIMEFRAMES[3]  # Default to '1 hour'
        self.current_symbol = None
        self.current_asset_type = None
        self.assets = {}
        self.data_loader_thread = None
        self.timeframe_data_cache = {}
        
        # Set up thread safety
        self._loading_lock = threading.Lock()
        self._chart_update_lock = threading.Lock()
        
        # Set up UI
        self.setup_ui()
        self.load_symbols()
        
        # Set up UI updater
        self.ui_updater = UIUpdater()
        self.ui_updater.update_progress.connect(self.update_progress_bar)
        self.ui_updater.update_chart.connect(self.update_chart_safely)
        
        # Connect chart signals if using LightweightChart
        if isinstance(self.chart, LightweightChart):
            self.chart.timeframe_changed.connect(self.on_timeframe_changed)
            self.current_timeframe = self.chart.current_timeframe
            
        self.center_on_screen()

    def setup_ui(self):
        # Main widget setup
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Create splitter for layout
        splitter = QSplitter(Qt.Horizontal)

        # Setup left column (asset selector and table)
        self.setup_left_column(splitter)
        
        # Setup right column (chart)
        self.setup_right_column(splitter)

        # Add splitter to main layout
        splitter.setSizes([400, 1200])
        self.main_layout.addWidget(splitter)

        # Setup status bar
        self.setup_status_bar()

    def setup_left_column(self, splitter):
        # Create left column widget
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # Asset selector
        self.setup_asset_selector(left_layout)

        # Search box
        self.setup_search_box(left_layout)

        # Table view
        self.setup_table_view(left_layout)

        splitter.addWidget(left_widget)

    def setup_right_column(self, splitter):
        # Create right column widget
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)

        # Chart
        self.chart = self.chart_type(self)
        self.chart.setMinimumSize(800, 600)
        right_layout.addWidget(self.chart)

        splitter.addWidget(right_widget)

    def setup_asset_selector(self, parent_layout):
        selector_layout = QHBoxLayout()
        selector_label = QLabel("Select Market Asset Type:")
        self.asset_selector = QComboBox()
        asset_types = list(MARKET_ASSET_TYPES.keys())
        self.asset_selector.addItems([asset_type.lower() for asset_type in asset_types])
        self.asset_selector.currentTextChanged.connect(self.on_asset_changed)
        
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.asset_selector)
        parent_layout.addLayout(selector_layout)

    def setup_search_box(self, parent_layout):
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Search...")
        self.search_box.returnPressed.connect(self.search)
        parent_layout.addWidget(self.search_box)

    def setup_table_view(self, parent_layout):
        self.table_view = QTableView()
        self.table_model = QStandardItemModel()
        headers = ["Symbol", "Last Price", "Change", "Change %", "Volume", "MA Cross Support", "MA Cross Resistance"]
        self.table_model.setHorizontalHeaderLabels(headers)
        
        # Setup proxy model for sorting
        self.proxy_model = NumericSortProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        
        # Configure table view
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Connect signals
        self.table_view.doubleClicked.connect(self.on_table_double_click)
        self.table_view.clicked.connect(self.on_table_click)
        
        parent_layout.addWidget(self.table_view)

    def setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("Loading... %p%")
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.setStatusBar(self.status_bar)

    def load_symbols(self):
        """Load symbols for all asset types."""
        self.symbols_by_asset = {}
        for asset_type, file_name in MARKET_ASSET_TYPES.items():
            try:
                with open(file_name, 'r') as f:
                    content = f.read().strip()
                    self.symbols_by_asset[asset_type.lower()] = [
                        symbol.strip() for symbol in content.split(',') if symbol.strip()
                    ]
            except IOError as e:
                logger.error(f"Error loading symbols for {asset_type}: {str(e)}")
                self.symbols_by_asset[asset_type.lower()] = []

    def on_asset_changed(self, asset_type):
        """Handle asset type change."""
        try:
            self.current_asset_type = asset_type.upper()
            symbols = self.symbols_by_asset.get(asset_type.lower(), [])
            
            # Update UI
            self.update_table(symbols)
            
            # Clear chart
            if isinstance(self.chart, LightweightChart):
                self.chart.reset_state()
            
            # Load new data
            self.load_data()
            
        except Exception as e:
            logger.error(f"Error changing asset type: {str(e)}")
            self.show_error_message(f"Failed to change asset type: {str(e)}")

    def on_timeframe_changed(self, new_timeframe, symbol):
        """Handle timeframe change."""
        try:
            with self._loading_lock:
                logger.info(f"Processing timeframe change to {new_timeframe} for {symbol}")
                
                # Stop existing data loader
                if self.data_loader_thread and self.data_loader_thread.isRunning():
                    self.data_loader_thread.stop()
                    self.data_loader_thread.wait()
                    self.data_loader_thread.deleteLater()
                
                # Create new data loader
                self.data_loader_thread = DataLoaderThread(
                    asset_type=self.current_asset_type,
                    symbols=symbol,
                    interval=new_timeframe
                )
                
                # Connect signals
                self.data_loader_thread.data_loaded.connect(
                    lambda data: self.handle_timeframe_data(data, new_timeframe, symbol)
                )
                self.data_loader_thread.progress_updated.connect(self.update_progress_bar)
                self.data_loader_thread.error_occurred.connect(self.on_data_load_error)
                
                # Start loading
                self.data_loader_thread.start()
                
        except Exception as e:
            logger.error(f"Error handling timeframe change: {str(e)}")
            self.show_error_message(f"Failed to update timeframe: {str(e)}")

    def handle_timeframe_data(self, data, timeframe, symbol):
        """Handle data loaded after timeframe change."""
        try:
            if symbol in data:
                df = data[symbol]
                if isinstance(df, pd.DataFrame) and not df.empty:
                    # Update cache
                    self.timeframe_data_cache[f"{symbol}_{timeframe}"] = df
                    
                    # Update chart
                    if isinstance(self.chart, LightweightChart):
                        self.chart.update_data(df, symbol, timeframe)
                    
                    # Update table
                    self.update_table_with_data({symbol: df})
                    
                    logger.info(f"Successfully updated display for {symbol} at {timeframe}")
                else:
                    logger.warning(f"No data available for {symbol} at {timeframe}")
                    self.show_error_message(
                        f"No data available for {symbol} in {timeframe} timeframe"
                    )
        except Exception as e:
            logger.error(f"Error handling timeframe data: {str(e)}")
            self.show_error_message("Error updating display with new timeframe data")

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
            logger.error(f"Error loading data: {str(e)}")
            self.show_error_message(f"Failed to load data: {str(e)}")

    def load_data_for_symbol(self, symbol, timeframe):
        """Load data for specific symbol and timeframe."""
        try:
            with self._loading_lock:
                if self.data_loader_thread and self.data_loader_thread.isRunning():
                    self.data_loader_thread.stop()
                    self.data_loader_thread.wait()
                    self.data_loader_thread.deleteLater()

                self.data_loader_thread = DataLoaderThread(
                    asset_type=self.current_asset_type,
                    symbols=symbol,
                    interval=timeframe
                )
                
                self.data_loader_thread.data_loaded.connect(
                    lambda data: self.handle_timeframe_data(data, timeframe, symbol)
                )
                self.data_loader_thread.progress_updated.connect(self.update_progress_bar)
                self.data_loader_thread.error_occurred.connect(self.on_data_load_error)
                
                self.data_loader_thread.start()
                logger.info(f"Started loading data for {symbol} at {timeframe}")
                
        except Exception as e:
            logger.error(f"Error loading symbol data: {str(e)}")
            self.show_error_message(f"Failed to load data for {symbol}")

    def on_data_loaded(self, data):
        """Handle initial data load."""
        try:
            self.assets = data
            self.update_table_with_data(data)
            self.update_progress_bar("Data loaded", 0, 100)
            logger.info("Data loaded and table updated")
        except Exception as e:
            logger.error(f"Error handling loaded data: {str(e)}")
            self.show_error_message("Failed to process loaded data")

    def update_chart_safely(self, df, symbol):
        """Update chart with thread safety."""
        try:
            with self._chart_update_lock:
                if isinstance(self.chart, LightweightChart):
                    self.chart.update_data(df, symbol, self.current_timeframe)
        except Exception as e:
            logger.error(f"Error updating chart: {str(e)}")
            self.show_error_message(f"Failed to update chart for {symbol}")

    # UI Update Methods
    def update_table(self, symbols):
        """Update table with new symbols."""
        self.table_model.clear()
        headers = ["Symbol", "Last Price", "Change", "Change %", "Volume", "MA Cross Support", "MA Cross Resistance"]
        self.table_model.setHorizontalHeaderLabels(headers)
        
        for symbol in symbols:
            row_items = [QStandardItem(symbol)]
            for _ in range(len(headers) - 1):
                row_items.append(QStandardItem(''))
            self.table_model.appendRow(row_items)

    def update_table_with_data(self, data):
        """Update table with market data."""
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
                        self.update_table_row(row, df, decimal_places)
                    else:
                        self.clear_table_row(row)
        except Exception as e:
            logger.error(f"Error updating table with data: {str(e)}")

    def update_table_row(self, row, df, decimal_places):
        """Update single table row with data."""
        try:
            df = self.calculate_ma(df)
            
            last_close = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else last_close
            change = last_close - prev_close
            change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
            volume = df['Volume'].iloc[-1]
            
            ma_cross_support, ma_cross_resistance = self.find_ma_cross_points(df)
            
            # Set table cells with numeric sorting
            self.set_table_numeric_cell(row, 1, last_close, f"{{:.{decimal_places}f}}")
            self.set_table_numeric_cell(row, 2, change, f"{{:.{decimal_places}f}}")
            self.set_table_numeric_cell(row, 3, change_percent, "{:.2f}%")
            self.set_table_numeric_cell(row, 4, volume, "{:.0f}")
            self.set_table_numeric_cell(row, 5, ma_cross_support, f"{{:.{decimal_places}f}}")
            self.set_table_numeric_cell(row, 6, ma_cross_resistance, f"{{:.{decimal_places}f}}")
            
        except Exception as e:
            logger.error(f"Error updating table row {row}: {str(e)}")
            self.clear_table_row(row)

    def set_table_numeric_cell(self, row, col, value, format_str):
        """Set table cell with numeric sorting capability."""
        try:
            if value is None or pd.isna(value):
                formatted_value = "N/A"
                sort_value = float('-inf')
            else:
                formatted_value = format_str.format(value)
                sort_value = float(value)

            item = QStandardItem(formatted_value)
            item.setData(sort_value, Qt.UserRole)
            self.table_model.setItem(row, col, item)
        except Exception as e:
            logger.error(f"Error setting table cell [{row},{col}]: {str(e)}")
            item = QStandardItem("N/A")
            item.setData(float('-inf'), Qt.UserRole)
            self.table_model.setItem(row, col, item)

    def clear_table_row(self, row):
        """Clear all cells in a table row."""
        for col in range(1, 7):
            item = QStandardItem("N/A")
            item.setData(float('-inf'), Qt.UserRole)
            self.table_model.setItem(row, col, item)

    def calculate_ma(self, df):
        """Calculate moving averages for dataframe."""
        df = df.copy()
        df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
        df['MA200'] = df['Close'].rolling(window=200, min_periods=1).mean()
        return df

    def find_ma_cross_points(self, df):
        """Find MA cross points for support and resistance."""
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

    def on_data_load_error(self, error_message):
        """Handle data loading errors."""
        QMessageBox.critical(self, "Error", f"Failed to load data: {error_message}")
        self.update_progress_bar("Data load failed", 0, 100)
        logger.error(f"Data load error: {error_message}")

    def show_error_message(self, message):
        """Show error message to user."""
        QMessageBox.warning(self, "Data Error", message)
        logger.warning(f"Error message shown: {message}")

    def update_progress_bar(self, message, min_value, max_value):
        """Update progress bar status."""
        self.progress_bar.setFormat(message)
        self.progress_bar.setRange(min_value, max_value)
        if max_value > 0:
            self.progress_bar.setValue(max_value)

    def search(self):
        """Search for symbol in table."""
        search_term = self.search_box.text().lower()
        for row in range(self.proxy_model.rowCount()):
            if search_term in self.proxy_model.data(self.proxy_model.index(row, 0)).lower():
                self.table_view.selectRow(row)
                return
        QMessageBox.information(self, "Search Result", "No matching symbol found.")

    def on_table_click(self, index):
        """Handle table row click."""
        symbol = self.proxy_model.data(self.proxy_model.index(index.row(), 0))
        self.current_symbol = symbol
        logger.info(f"Selected symbol: {symbol}")

    def on_table_double_click(self, index):
        """Handle table row double click."""
        symbol = self.proxy_model.data(self.proxy_model.index(index.row(), 0))
        self.act_on_row(symbol)

    def act_on_row(self, symbol):
        """Handle table row action."""
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

    def center_on_screen(self):
        """Center window on screen."""
        screen_geometry = QDesktopWidget().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def closeEvent(self, event):
        """Handle application close event."""
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
        """Handle key press events."""
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