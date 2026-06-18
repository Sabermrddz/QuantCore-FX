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
        
        # Set Fusion style
        app.setStyle('Fusion')

        # Global professional stylesheet
        app.setStyleSheet(f"""
            /*****************************************************************
             * APEX Professional Trading System — Global Stylesheet
             *****************************************************************/

            /* ----- Root / Background ----- */
            QMainWindow {{
                background-color: #f0f2f5;
            }}
            QWidget {{
                font-family: "Segoe UI", "Arial", sans-serif;
                font-size: 13px;
                color: #2c3e50;
            }}

            /* ----- Tab Widget (Navigation Bar) ----- */
            QTabWidget::pane {{
                border: none;
                background: #f0f2f5;
                top: -1px;
            }}
            QTabBar::tab {{
                background: #2c3e50;
                color: #95a5a6;
                padding: 10px 22px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: #f0f2f5;
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
            }}
            QTabBar::tab:hover:!selected {{
                background: #34495e;
                color: #ecf0f1;
            }}

            /* ----- Cards (QFrame) ----- */
            QFrame#card {{
                background-color: #ffffff;
                border: 1px solid #e0e4e8;
                border-radius: 10px;
                padding: 18px;
            }}
            QFrame#card:hover {{
                border-color: #c0c8d0;
            }}
            QFrame#statusCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ffffff, stop:1 #f8f9fb);
                border: 1px solid #e0e4e8;
                border-radius: 10px;
                padding: 20px;
            }}

            /* ----- Labels ----- */
            QLabel {{
                color: #2c3e50;
            }}
            QLabel[heading="true"] {{
                font-size: 16px;
                font-weight: 700;
                color: #1a1a2e;
                padding-bottom: 4px;
            }}
            QLabel[subheading="true"] {{
                font-size: 13px;
                font-weight: 600;
                color: #7f8c8d;
                letter-spacing: 1px;
            }}
            QLabel[value="true"] {{
                font-size: 28px;
                font-weight: 700;
            }}

            /* ----- Tables ----- */
            QTableWidget {{
                background-color: #ffffff;
                border: 1px solid #e0e4e8;
                border-radius: 8px;
                gridline-color: #f0f2f5;
                selection-background-color: #ebf5fb;
                selection-color: #2c3e50;
                padding: 4px;
            }}
            QTableWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid #f0f2f5;
            }}
            QTableWidget::item:selected {{
                background-color: #ebf5fb;
                color: #2c3e50;
            }}
            QHeaderView::section {{
                background-color: #f8f9fb;
                color: #7f8c8d;
                font-weight: 600;
                font-size: 12px;
                text-transform: uppercase;
                padding: 8px 10px;
                border: none;
                border-bottom: 2px solid #e0e4e8;
            }}

            /* ----- Buttons ----- */
            QPushButton {{
                background-color: #3498db;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
            QPushButton:pressed {{
                background-color: #2471a3;
            }}
            QPushButton:disabled {{
                background-color: #bdc3c7;
                color: #95a5a6;
            }}

            QPushButton#success {{
                background-color: #27ae60;
            }}
            QPushButton#success:hover {{
                background-color: #229954;
            }}
            QPushButton#success:disabled {{
                background-color: #bdc3c7;
            }}

            QPushButton#danger {{
                background-color: #e74c3c;
            }}
            QPushButton#danger:hover {{
                background-color: #cb4335;
            }}

            QPushButton#secondary {{
                background-color: #95a5a6;
            }}
            QPushButton#secondary:hover {{
                background-color: #7f8c8d;
            }}

            /* ----- Progress Bar ----- */
            QProgressBar {{
                background-color: #ecf0f1;
                border: none;
                border-radius: 6px;
                height: 18px;
                text-align: center;
                font-size: 12px;
                font-weight: 600;
                color: #2c3e50;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2ecc71);
                border-radius: 6px;
            }}

            /* ----- Combo Box / Spinner ----- */
            QComboBox {{
                background-color: #ffffff;
                border: 1px solid #d5d8dc;
                border-radius: 6px;
                padding: 6px 12px;
                min-height: 20px;
            }}
            QComboBox:hover {{
                border-color: #3498db;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QDoubleSpinBox, QSpinBox, QLineEdit {{
                background-color: #ffffff;
                border: 1px solid #d5d8dc;
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 20px;
            }}
            QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {{
                border-color: #3498db;
            }}

            /* ----- Group Box ----- */
            QGroupBox {{
                font-size: 14px;
                font-weight: 700;
                color: #2c3e50;
                border: 1px solid #e0e4e8;
                border-radius: 10px;
                margin-top: 12px;
                padding: 20px 16px 16px 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 12px;
                background-color: #f0f2f5;
                border-radius: 4px;
                margin-left: 10px;
            }}

            /* ----- Scroll Area ----- */
            QScrollArea {{
                border: none;
                background: transparent;
            }}

            /* ----- Check Box ----- */
            QCheckBox {{
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #bdc3c7;
            }}
            QCheckBox::indicator:checked {{
                background-color: #3498db;
                border-color: #3498db;
            }}

            /* ----- Tooltip ----- */
            QToolTip {{
                background-color: #2c3e50;
                color: #ffffff;
                border: none;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 12px;
            }}

            /* ----- Status Bar ----- */
            QStatusBar {{
                background-color: #2c3e50;
                color: #ecf0f1;
                font-size: 12px;
            }}
        """)
        
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
