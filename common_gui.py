import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTableView, QSplitter, QStatusBar, 
                             QProgressBar, QComboBox, QHeaderView, QMessageBox,
                             QDesktopWidget, QLineEdit, QShortcut, QDateEdit,
                             QLabel, QAbstractItemView)
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QDate, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QKeySequence

from chart_types import LightweightChart, NativeChart
from config import MARKET_ASSET_TYPES, TIMEFRAMES

logger = logging.getLogger(__name__)

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
        self.assets = {}
        self.current_symbol = None
        self.current_timeframe = "1D"
        self.latest_bar_date = None
        self.ui_updater = UIUpdater()
        self.ui_updater.update_progress.connect(self.update_progress_bar)
        self.ui_updater.update_chart.connect(self.update_chart_safely)
        self.load_symbols()
        self.setup_ui()
        self.load_data() 

    def setup_ui(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout()
        splitter = QSplitter(Qt.Horizontal)
        column1_widget = QWidget()
        column1_layout = QVBoxLayout(column1_widget)
        asset_selector_layout = QHBoxLayout()
        asset_selector_label = QLabel("Select Market Asset Type:")
        self.asset_selector = QComboBox()
        asset_types = list(MARKET_ASSET_TYPES.keys())
        self.asset_selector.addItems([asset_type.lower() for asset_type in asset_types])
        asset_selector_layout.addWidget(asset_selector_label)
        asset_selector_layout.addWidget(self.asset_selector)
        column1_layout.addLayout(asset_selector_layout)
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Search...")
        self.search_box.returnPressed.connect(self.search)
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self.show_search_box)
        self.esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.esc_shortcut.activated.connect(self.hide_search_box)
        column1_layout.addWidget(self.search_box)
        default_index = asset_types.index('CRYPTO')
        self.asset_selector.setCurrentIndex(default_index)
        self.table_view = QTableView()
        self.table_model = QStandardItemModel()
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
        column1_layout.addWidget(self.table_view)
        column2_widget = QWidget()
        column2_layout = QVBoxLayout(column2_widget)
        timeframe_layout = QHBoxLayout()
        timeframes = ['1W', '1D', '4H', '1H', '30M', '15M', '5M']
        for tf in timeframes:
            btn = QPushButton(tf)
            btn.clicked.connect(lambda checked, t=tf: self.change_timeframe(t))
            timeframe_layout.addWidget(btn)
        column2_layout.addLayout(timeframe_layout)
        date_layout = QHBoxLayout()
        self.date_picker = QDateEdit(calendarPopup=True)
        self.date_picker.setDisplayFormat("yyyy-MM-dd")
        self.date_picker.setDate(QDate.currentDate())
        self.update_data_button = QPushButton('Load')
        self.update_data_button.clicked.connect(self.update_data)
        self.current_data_button = QPushButton('Load today')
        self.current_data_button.clicked.connect(self.update_current_data)
        date_layout.addWidget(self.date_picker)
        date_layout.addWidget(self.update_data_button)
        date_layout.addWidget(self.current_data_button)
        column2_layout.addLayout(date_layout)
        if self.chart_type == LightweightChart:
            self.chart = self.chart_type(self)
        elif self.chart_type == NativeChart:
            self.chart = self.chart_type(self, width=8, height=4, dpi=150)
        column2_layout.addWidget(self.chart)
        splitter.addWidget(column1_widget)
        splitter.addWidget(column2_widget)
        splitter.setSizes([400, 1200])
        self.main_layout.addWidget(splitter)
        self.main_widget.setLayout(self.main_layout)
        self.asset_selector.setCurrentIndex(0)
        self.asset_selector.currentTextChanged.connect(self.on_asset_changed)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar() # progress_bar initialization 
        self.progress_bar.setFormat("Loading... %p%")
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.progress_bar)

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
        symbols = self.symbols_by_asset.get(asset_type.lower(), [])
        self.update_table(symbols)
        self.data_loader.contract_type = asset_type.upper()
        self.load_data() 

    def update_table(self, symbols):
        self.table_model.clear()
        headers = ["Symbol", "15 mins Res", "15 mins Sup", "30 mins Res", "30 mins Sup", 
                   "1 hour Res", "1 hour Sup", "4 hours Res", "4 hours Sup"]
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
        self.current_timeframe = "1D"
        self.latest_bar_date = None
        if symbol in self.assets:
            selected_df = self.assets[symbol]
            if isinstance(selected_df, pd.DataFrame) and not selected_df.empty:
                self.update_chart_safely(selected_df, symbol)
            else:
                logger.warning(f"Invalid DataFrame for symbol: {symbol}")
        else:
            logger.warning(f"No data available for symbol: {symbol}")

    def load_data(self):
        selected_date = self.date_picker.date().toPyDate()
        start_date = selected_date - timedelta(days=36 * 22) 
        asset_type = self.asset_selector.currentText().upper()
        self.assets = self.data_loader.load_data(start_date.strftime("%Y%m%d"), selected_date.strftime("%Y%m%d"))
        self.update_table_with_data()
        self.update_progress_bar("Data loaded", 0, 100)

    def update_table_with_data(self):
        for row in range(self.table_model.rowCount()):
            symbol = self.table_model.item(row, 0).text()
            if symbol in self.assets:
                df = self.assets[symbol]
                if isinstance(df, pd.DataFrame) and not df.empty:
                    last_close = df['Close'].iloc[-1]
                    self.table_model.setItem(row, 1, QStandardItem(str(last_close)))

    def update_data(self):
        selected_date = self.date_picker.date().toPyDate()
        start_date = selected_date - timedelta(days=36 * 22)
        self.assets = self.data_loader.load_data(start_date.strftime("%Y%m%d"), selected_date.strftime("%Y%m%d"))
        self.update_progress_bar("Data updated", 0, 100)
        if self.current_symbol:
            self.act_on_row(self.current_symbol)

    def update_current_data(self):
        self.date_picker.setDate(QDate.currentDate())
        self.update_data()

    def change_timeframe(self, timeframe):
        if self.current_symbol:
            self.current_timeframe = timeframe

    def update_progress_bar(self, message, min_value, max_value):
        self.progress_bar.setFormat(message)
        self.progress_bar.setRange(min_value, max_value)
        if max_value > 0:
            self.progress_bar.setValue(max_value)

    def update_chart_safely(self, df, symbol):
        if df is not None and not df.empty:
            try:
                self.chart.set(df, symbol)
                logger.info(f"Successfully updated chart for {symbol}")
            except Exception as e:
                logger.error(f"Error updating chart for {symbol}: {str(e)}")
        else:
            logger.warning(f"Cannot update chart: Empty or None DataFrame for {symbol}")

    def search(self):
        search_term = self.search_box.text().lower()
        for row in range(self.proxy_model.rowCount()):
            if search_term in self.proxy_model.data(self.proxy_model.index(row, 0)).lower():
                self.table_view.selectRow(row)
                return
        QMessageBox.information(self, "Search Result", "No matching symbol found.")

    def show_search_box(self):
        self.search_box.clear()
        self.search_box.setFocus()

    def hide_search_box(self):
        self.search_box.clear()

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