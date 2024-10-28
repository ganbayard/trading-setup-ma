import argparse
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
import sys
from common_gui import MainWindow
from chart_types import LightweightChart
import multiprocessing
from config import MARKET_ASSET_TYPES
from market_scheduler import MarketScheduler

class TradingApp(MainWindow):
    def __init__(self, chart_type=None):
        super().__init__(chart_type)
        self.init_scheduler()
        self.setWindowTitle("Market Asset Viewer - Auto-updating")

    def init_scheduler(self):
        """Initialize and start the market data scheduler"""
        try:
            self.scheduler = MarketScheduler()
            
            # Connect scheduler signals
            self.scheduler.update_complete.connect(self.on_data_update_complete)
            self.scheduler.update_error.connect(self.on_data_update_error)
            
            # Start scheduler
            self.scheduler.start()
            
            # Schedule default updates
            self.setup_default_schedules()
        except Exception as e:
            QMessageBox.critical(self, "Scheduler Error", 
                               f"Failed to initialize scheduler: {str(e)}")

    def setup_default_schedules(self):
        """Set up default scheduling for different market types"""
        try:
            # Schedule crypto updates every 5 minutes
            self.scheduler.schedule_crypto_update(interval_minutes=5)
            
            # Schedule stock market updates at market close (5 PM) on weekdays
            self.scheduler.schedule_market_update("STOCK", "0 17 * * 1-5")
            
            # Schedule forex updates every hour during trading days
            self.scheduler.schedule_market_update("FOREX", "0 * * * 1-5")
            
            # Schedule other market types as needed
            for asset_type in ["COMMODITY", "INDEX", "FUTURE"]:
                self.scheduler.schedule_market_update(asset_type, "0 17 * * 1-5")
            
            self.statusBar().showMessage("Market data updates scheduled", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Scheduling Error", 
                              f"Failed to set up market data updates: {str(e)}")

    def on_data_update_complete(self, job_id):
        """Handle completed data updates"""
        try:
            self.statusBar().showMessage(f"Market data update completed: {job_id}", 3000)
            # Reload data for current view if it matches the updated asset type
            current_asset = self.asset_selector.currentText().upper()
            if (current_asset == "CRYPTO" and job_id == "crypto_update") or \
               (current_asset in job_id.upper()):
                self.load_data()
        except Exception as e:
            logger.error(f"Error handling update completion: {str(e)}")

    def on_data_update_error(self, error_msg):
        """Handle data update errors"""
        self.statusBar().showMessage(f"Update error: {error_msg}", 5000)
        QMessageBox.warning(self, "Update Error", error_msg)

    def closeEvent(self, event):
        """Handle application close"""
        try:
            # Stop the scheduler gracefully
            if hasattr(self, 'scheduler'):
                self.scheduler.stop()
            
            # Handle other cleanup
            super().closeEvent(event)
        except Exception as e:
            print(f"Error during shutdown: {str(e)}")
            event.accept()  # Ensure the application closes even if there's an error

def main():
    parser = argparse.ArgumentParser(description="Market Asset Viewer")
    parser.add_argument('-a', '--asset',
                        choices=list(MARKET_ASSET_TYPES.keys()),
                        default='CRYPTO',
                        help='Choose asset type')
    args = parser.parse_args()

    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass

    app = QApplication(sys.argv)
    
    # Enable High DPI scaling
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    # Create TradingApp instance with chart_type
    main_window = TradingApp(chart_type=LightweightChart)
    main_window.show()
    
    # Set initial asset type from command line argument
    main_window.asset_selector.setCurrentText(args.asset.lower())
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
