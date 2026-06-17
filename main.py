"""
APEX Layer 1 — Application Entry Point

Launches the PyQt5 application.

Usage:
    python main.py

Requirements:
    - Python 3.10+
    - PyQt5 5.15+
    - requests 2.31+
    - pandas 2.0+
    - python-dotenv 1.0+
    - openpyxl 3.1+

Installation:
    pip install -r requirements.txt

First run:
    1. Ensure .env file exists with FRED_API_KEY set
    2. (Optional for Layer 2) MetaTrader 5 terminal running
    3. Run: python main.py
    4. App initializes database with schema
    5. Auto-fetches rates from FRED if AUTO_FETCH_RATES_ON_STARTUP=true
    6. Ready for manual CPI/PMI entry
"""

import sys
import traceback
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
import config
from main_window import MainWindow


def main():
    """Application entry point."""
    try:
        # Check critical configuration
        if not config.FRED_API_KEY:
            print("[ERROR] FRED_API_KEY not configured in .env file")
            print("Please:")
            print("  1. Go to https://fred.stlouisfed.org")
            print("  2. Register and get a free API key")
            print("  3. Add to .env: FRED_API_KEY=your_key_here")
            return 1
        
        if config.DEBUG:
            print(f"[Main] {config.APP_TITLE}")
            print(f"[Main] Debug: ON")
            print(f"[Main] Database: {config.DB_PATH}")
        
        # Create QApplication
        app = QApplication(sys.argv)
        
        # Set application-wide stylesheet (optional)
        app.setStyle('Fusion')
        
        # Create and show main window
        window = MainWindow()
        window.show()
        
        # Run application
        exit_code = app.exec_()
        
        if config.DEBUG:
            print("[Main] Application closed normally")
        
        return exit_code
        
    except Exception as e:
        # Show error dialog
        print(f"[CRITICAL ERROR] {str(e)}")
        traceback.print_exc()
        
        # Try to show Qt error dialog
        try:
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            QMessageBox.critical(
                None,
                "Critical Error",
                f"Application failed to start:\n\n{str(e)}\n\nCheck the console for details."
            )
        except:
            pass
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
