"""
APEX Layer 1 — Main Application Window

Assembles all 4 tabs:
- Tab 1: Dashboard (main signal + ranking table)
- Tab 2: Monthly Entry (CPI + PMI input form)
- Tab 3: History (past signals)
- Tab 4: Settings (configuration)

Responsibilities:
- Create QMainWindow with QTabWidget
- Instantiate all UI tabs
- Manage database connection
- Run FRED API fetch in background thread (QThread)
- Connect inter-tab signals (e.g., entry tab saves → dashboard tab refreshes)
- Handle window events and cleanup
"""

from PyQt5.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget, QMessageBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from typing import Dict, Optional
import config
from database import Database
from fred_client import FredClient
from ui.dashboard_tab import DashboardTab
from ui.entry_tab import MonthlyEntryTab
from ui.history_tab import HistoryTab
from ui.settings_tab import SettingsTab


class FredFetchWorker(QThread):
    """Background worker thread for fetching rates from FRED API."""
    
    # Signals
    rates_fetched = pyqtSignal(dict)  # Emitted with {currency: rate} dict
    error_occurred = pyqtSignal(str)   # Emitted on error
    
    def __init__(self, db: Database):
        """
        Initialize FRED fetch worker.
        
        Args:
            db: Database instance to save rates
        """
        super().__init__()
        self.db = db
        self.client = FredClient()
    
    def run(self):
        """
        Fetch rates from FRED API and save to database.
        """
        try:
            if config.DEBUG:
                print("[Worker] Starting FRED rate fetch...")
            
            rates = self.client.fetch_all_rates()
            
            # Save to database
            for currency, rate in rates.items():
                if rate is not None:
                    self.db.upsert_rate(currency, rate, source="FRED")
            
            if config.DEBUG:
                print("[Worker] FRED fetch complete")
            
            self.rates_fetched.emit(rates)
            
        except Exception as e:
            error_msg = f"FRED fetch error: {str(e)}"
            if config.DEBUG:
                print(f"[Worker] {error_msg}")
            self.error_occurred.emit(error_msg)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        
        # Initialize database
        try:
            self.db = Database()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to initialize database: {e}\n\nPlease check your configuration."
            )
            raise
        
        # UI components
        self.dashboard_tab = None
        self.entry_tab = None
        self.history_tab = None
        self.settings_tab = None
        
        # Worker thread
        self.fred_worker = None
        
        self._init_ui()
        self._connect_signals()
        self._setup_auto_fetch()
    
    def _init_ui(self):
        """Build the main window UI."""
        self.setWindowTitle(config.APP_TITLE)
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        # Tab widget
        tabs = QTabWidget()
        
        # Tab 1: Dashboard
        self.dashboard_tab = DashboardTab(self.db)
        tabs.addTab(self.dashboard_tab, config.TAB_NAMES["dashboard"])
        
        # Tab 2: Monthly Entry
        self.entry_tab = MonthlyEntryTab(self.db)
        tabs.addTab(self.entry_tab, config.TAB_NAMES["entry"])
        
        # Tab 3: History
        self.history_tab = HistoryTab(self.db)
        tabs.addTab(self.history_tab, config.TAB_NAMES["history"])
        
        # Tab 4: Settings
        self.settings_tab = SettingsTab()
        tabs.addTab(self.settings_tab, config.TAB_NAMES["settings"])
        
        # Set main widget
        self.setCentralWidget(tabs)
        
        # Style tabs
        tab_font = QFont("Arial", 11)
        tabs.setFont(tab_font)
    
    def _connect_signals(self):
        """Connect inter-tab signals."""
        # Entry tab saves data → Dashboard tab refreshes
        self.entry_tab.data_saved.connect(self.dashboard_tab.on_data_saved)
        
        # Entry tab saves data → History tab refreshes
        self.entry_tab.data_saved.connect(self.history_tab.refresh_history)
        
        # Dashboard requests FRED fetch → Start worker thread
        self.dashboard_tab.fetch_rates_requested.connect(self._fetch_rates)
    
    def _setup_auto_fetch(self):
        """Auto-fetch rates on startup if enabled."""
        if config.AUTO_FETCH_RATES_ON_STARTUP:
            if config.DEBUG:
                print("[Main] Auto-fetch enabled, fetching rates on startup...")
            self._fetch_rates()
    
    def _fetch_rates(self):
        """
        Trigger background FRED rate fetch.
        Emits results to dashboard when complete.
        """
        if self.fred_worker is not None and self.fred_worker.isRunning():
            # Already fetching
            return
        
        self.fred_worker = FredFetchWorker(self.db)
        self.fred_worker.rates_fetched.connect(self._on_rates_fetched)
        self.fred_worker.error_occurred.connect(self._on_fetch_error)
        self.fred_worker.start()
    
    def _on_rates_fetched(self, rates: Dict[str, Optional[float]]):
        """
        Handle successful FRED fetch.
        
        Args:
            rates: Dict mapping currency to rate
        """
        if config.DEBUG:
            print("[Main] Rates fetched successfully, updating dashboard...")
        
        # Update dashboard display
        self.dashboard_tab.on_rates_updated(rates)
    
    def _on_fetch_error(self, error_msg: str):
        """
        Handle FRED fetch error.
        
        Args:
            error_msg: Error message string
        """
        print(f"[ERROR] {error_msg}")
        # Don't show error message to user; display gracefully in dashboard
    
    def closeEvent(self, event):
        """Handle window close event."""
        try:
            # Stop any running threads
            if self.fred_worker is not None and self.fred_worker.isRunning():
                self.fred_worker.quit()
                self.fred_worker.wait()
            
            # Close database
            self.db.close()
            
            event.accept()
        except Exception as e:
            print(f"[ERROR] Error during shutdown: {e}")
            event.accept()
