import argparse
from PyQt5.QtWidgets import QApplication
import sys
from common_gui import MainWindow
from data_sources import get_data_loader
from chart_types import load_chart_type
import multiprocessing
from config import MARKET_ASSET_TYPES

def main():
    parser = argparse.ArgumentParser(description="Market Asset Viewer")
    parser.add_argument('-t', '--type', 
                        choices=['lightweight', 'nativechart'], 
                        default='lightweight', 
                        help='Choose chart type (lightweight or nativechart)')
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
    data_loader = get_data_loader(args.asset)
    chart_type = load_chart_type(args.type)
    main_window = MainWindow(data_loader, chart_type)
    main_window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()