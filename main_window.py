"""
APEX Professional Trading System — Main Application Window

Assembles all 6 tabs:
- Tab 1: Dashboard (Layer 1 fundamental signals)
- Tab 2: Monthly Entry (CPI + PMI data input)
- Tab 3: Layer 2 Monitor (real-time technical analysis)
- Tab 4: Confluence Signals (merged Layer 1 + Layer 2)
- Tab 5: History (past signals)
- Tab 6: Settings (configuration)

Responsibilities:
- Create QMainWindow with QTabWidget
- Instantiate all UI tabs
- Manage database connection
- Run FRED API fetch in background thread
- Run Alpha Vantage real-time data fetching
- Connect inter-tab signals
- Handle window events and cleanup
"""

from PyQt5.QtWidgets import QMainWindow, QTabWidget, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QFont
from typing import Dict, Optional
import config
from database import Database
from layer2_technical import TechnicalAnalyzer
from ui.dashboard_tab import DashboardTab
from ui.entry_tab import MonthlyEntryTab
from ui.layer2_monitor_tab import Layer2MonitorTab
from ui.confluence_tab import ConfluenceSignalsTab
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
    """Main application window — Professional hybrid trading system."""
    
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
        
        # Initialize Layer 2 components
        self.tech_analyzer = TechnicalAnalyzer(lookback=config.Z_SCORE_LOOKBACK)
        
        # UI components
        self.dashboard_tab = None
        self.entry_tab = None
        self.layer2_tab = None
        self.confluence_tab = None
        self.history_tab = None
        self.settings_tab = None
        
        # Worker threads
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
        
        # Tab 1: Dashboard (Layer 1)
        self.dashboard_tab = DashboardTab(self.db)
        tabs.addTab(self.dashboard_tab, config.TAB_NAMES["dashboard"])
        
        # Tab 2: Monthly Entry (Data input)
        self.entry_tab = MonthlyEntryTab(self.db)
        tabs.addTab(self.entry_tab, config.TAB_NAMES["entry"])
        
        # Tab 3: Layer 2 Monitor (Real-time technical)
        self.layer2_tab = Layer2MonitorTab(self.tech_analyzer)
        tabs.addTab(self.layer2_tab, config.TAB_NAMES["layer2"])
        
        # Tab 4: Confluence Signals (Layer 1 + Layer 2)
        self.confluence_tab = ConfluenceSignalsTab(self.db, self.tech_analyzer)
        tabs.addTab(self.confluence_tab, config.TAB_NAMES["confluence"])
        
        # Tab 5: History
        self.history_tab = HistoryTab(self.db)
        tabs.addTab(self.history_tab, config.TAB_NAMES["history"])
        
        # Tab 6: Settings
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
        
        # Dashboard generates signal → Confluence tab receives signal
        self.dashboard_tab.signal_generated.connect(self._on_dashboard_signal)
        
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
    
    def _on_dashboard_signal(self, strongest: str, weakest: str, gap: float,
                              bias_matrix: dict = None):
        """
        Handle dashboard signal generation.
        Pass to confluence tab for Layer 2 analysis.

        Args:
            strongest: Strongest currency
            weakest: Weakest currency
            gap: Gap score
            bias_matrix: Monthly directional bias matrix from Layer 1
        """
        if config.DEBUG:
            print(f"[Main] Signal generated: {strongest}/{weakest} gap={gap:.1f}")

        # Update confluence tab with new Layer 1 signal + bias matrix
        self.confluence_tab.set_layer1_signal(strongest, weakest, gap, bias_matrix)
    
    def closeEvent(self, event):
        """Handle window close event."""
        try:
            # Stop any running threads
            if self.fred_worker is not None and self.fred_worker.isRunning():
                self.fred_worker.quit()
                self.fred_worker.wait()
            
            # Stop Layer 2 monitoring
            if self.layer2_tab:
                self.layer2_tab.closeEvent(event)
            
            # Close database
            self.db.close()
            
            event.accept()
        except Exception as e:
            print(f"[ERROR] Error during shutdown: {e}")
            event.accept()
