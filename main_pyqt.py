import argparse
from PyQt5.QtWidgets import QApplication
import sys
from common_gui import MainWindow
from chart_types import LightweightChart
import multiprocessing
from config import MARKET_ASSET_TYPES

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
    # Create MainWindow instance with chart_type
    main_window = MainWindow(chart_type=LightweightChart)
    main_window.show()
    
    # Set initial asset type from command line argument
    main_window.asset_selector.setCurrentText(args.asset.lower())
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()