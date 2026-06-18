"""
APEX Layer 1 — Tab 4: Settings

Configuration editor for:
- FRED API key (with test connection)
- Central Bank inflation targets (read-only display, edit only if CB changes mandate)
- Scoring weights (Rate %, CPI %, PMI %)
- Minimum gap to trade
- Auto-fetch rates on startup toggle
- Application info

Settings are stored in the .env file.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDoubleSpinBox,
    QPushButton, QCheckBox, QGroupBox, QSpinBox, QMessageBox, QScrollArea
)
from PyQt5.QtCore import pyqtSignal, QThread
from PyQt5.QtGui import QFont
from typing import Optional
import config
from data_feeder import Mt5DataFeeder
from fred_client import FredClient
from pathlib import Path


class FredTestWorker(QThread):
    """Background thread for testing FRED API connection."""
    
    test_complete = pyqtSignal(bool, str)  # (success, message)
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
    
    def run(self):
        """Test FRED connectivity."""
        try:
            client = FredClient(self.api_key, timeout=5)
            rate = client.fetch_rate("USD")
            
            if rate is not None:
                self.test_complete.emit(True, f"✓ Connection successful! USD rate: {rate}%")
            else:
                self.test_complete.emit(False, "✗ No data returned for USD")
        except Exception as e:
            self.test_complete.emit(False, f"✗ Connection failed: {str(e)}")


class Mt5TestWorker(QThread):
    """Background thread for testing MT5 connection."""

    test_complete = pyqtSignal(bool, str)

    def __init__(self, symbol_suffix: str):
        super().__init__()
        self.symbol_suffix = symbol_suffix

    def run(self):
        try:
            feeder = Mt5DataFeeder(symbol_suffix=self.symbol_suffix)
            if feeder.initialize():
                price = feeder.get_current_price("EUR_USD")
                if price:
                    self.test_complete.emit(True, f"✓ Connected! EUR/USD bid={price['bid']:.5f} ask={price['ask']:.5f}")
                else:
                    self.test_complete.emit(True, "✓ Connected! (no EUR/USD tick data)")
                feeder.shutdown()
            else:
                self.test_complete.emit(False, f"✗ {feeder.last_error}")
        except Exception as e:
            self.test_complete.emit(False, f"✗ {e}")


class SettingsTab(QWidget):
    """Settings and configuration tab."""
    
    # Signal triggered when settings change
    settings_changed = pyqtSignal()
    
    def __init__(self):
        """Initialize Settings tab."""
        super().__init__()
        self.env_path = Path(__file__).parent.parent / ".env"
        
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        """Build the UI layout."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # ====== FRED API Configuration ======
        api_group = QGroupBox("FRED API Configuration")
        api_layout = QVBoxLayout()
        
        api_layout.addWidget(QLabel(
            "Enter your FRED API key for automatic interest rate fetching.\n"
            "Get a free key from https://fred.stlouisfed.org"
        ))
        
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Paste your FRED API key here...")
        key_layout.addWidget(self.api_key_input)
        
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_fred_connection)
        key_layout.addWidget(test_btn)
        
        api_layout.addLayout(key_layout)
        
        self.test_status = QLabel("")
        self.test_status.setStyleSheet("color: #95a5a6; font-style: italic;")
        api_layout.addWidget(self.test_status)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        layout.addSpacing(10)
        
        # ====== MetaTrader 5 Connection ======
        mt5_group = QGroupBox("MetaTrader 5 (Layer 2 Forex Data)")
        mt5_layout = QVBoxLayout()
        mt5_layout.addWidget(QLabel(
            "MT5 provides real-time forex data from your local MetaTrader 5 terminal.\n"
            "Ensure MT5 is installed and running with a demo/live account.\n"
            "Symbol suffix is used by some brokers (e.g., .m for OANDA MT5)."
        ))
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("Symbol Suffix:"))
        self.mt5_suffix_input = QLineEdit()
        self.mt5_suffix_input.setPlaceholderText("e.g., .m (leave empty if unsure)")
        suffix_layout.addWidget(self.mt5_suffix_input)
        mt5_layout.addLayout(suffix_layout)
        mt5_status_layout = QHBoxLayout()
        self.mt5_status_label = QLabel("Status: Not tested")
        self.mt5_status_label.setStyleSheet("color: #95a5a6; font-style: italic;")
        mt5_status_layout.addWidget(self.mt5_status_label)
        mt5_test_btn = QPushButton("Test Connection")
        mt5_test_btn.clicked.connect(self._test_mt5_connection)
        mt5_status_layout.addWidget(mt5_test_btn)
        mt5_layout.addLayout(mt5_status_layout)
        mt5_group.setLayout(mt5_layout)
        layout.addWidget(mt5_group)
        layout.addSpacing(10)
        
        # ====== Central Bank Targets ======
        cb_group = QGroupBox("Central Bank Inflation Targets (%)")
        cb_layout = QVBoxLayout()
        
        cb_layout.addWidget(QLabel(
            "These are hardcoded constants. Edit only if a central bank officially changes its mandate.\n"
            "Most central banks maintain these targets for years."
        ))
        
        # Display in a grid-like format
        targets_text = "  ".join([f"{c}: {config.CB_TARGETS[c]}%" for c in config.CURRENCIES])
        targets_label = QLabel(targets_text)
        targets_label.setFont(QFont("Courier", 10))
        targets_label.setStyleSheet("background-color: #ecf0f1; padding: 10px; border-radius: 4px;")
        cb_layout.addWidget(targets_label)
        
        cb_layout.addWidget(QLabel("To edit: Manually update the CB_TARGETS dict in config.py"))
        cb_group.setLayout(cb_layout)
        layout.addWidget(cb_group)
        layout.addSpacing(10)
        
        # ====== Scoring Weights ======
        weights_group = QGroupBox("Scoring Weights")
        weights_layout = QVBoxLayout()
        
        weights_layout.addWidget(QLabel(
            "Adjust the influence of each input. Must sum to 100%.\n"
            "Default: Rate 50%, CPI 30%, PMI 20%"
        ))
        
        # Rate weight
        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel("Rate Differential:"))
        self.weight_rate_spin = QDoubleSpinBox()
        self.weight_rate_spin.setRange(0, 100)
        self.weight_rate_spin.setValue(config.WEIGHT_RATE * 100)
        self.weight_rate_spin.setSuffix("%")
        self.weight_rate_spin.setDecimals(1)
        rate_layout.addWidget(self.weight_rate_spin)
        rate_layout.addStretch()
        weights_layout.addLayout(rate_layout)
        
        # CPI weight
        cpi_layout = QHBoxLayout()
        cpi_layout.addWidget(QLabel("CPI Deviation:"))
        self.weight_cpi_spin = QDoubleSpinBox()
        self.weight_cpi_spin.setRange(0, 100)
        self.weight_cpi_spin.setValue(config.WEIGHT_CPI * 100)
        self.weight_cpi_spin.setSuffix("%")
        self.weight_cpi_spin.setDecimals(1)
        cpi_layout.addWidget(self.weight_cpi_spin)
        cpi_layout.addStretch()
        weights_layout.addLayout(cpi_layout)
        
        # PMI weight
        pmi_layout = QHBoxLayout()
        pmi_layout.addWidget(QLabel("PMI Composite:"))
        self.weight_pmi_spin = QDoubleSpinBox()
        self.weight_pmi_spin.setRange(0, 100)
        self.weight_pmi_spin.setValue(config.WEIGHT_PMI * 100)
        self.weight_pmi_spin.setSuffix("%")
        self.weight_pmi_spin.setDecimals(1)
        pmi_layout.addWidget(self.weight_pmi_spin)
        pmi_layout.addStretch()
        weights_layout.addLayout(pmi_layout)
        
        # Total validation label
        self.weights_total_label = QLabel("Total: 0%")
        self.weights_total_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        weights_layout.addWidget(self.weights_total_label)
        
        # Connect to update total
        self.weight_rate_spin.valueChanged.connect(self._update_weights_total)
        self.weight_cpi_spin.valueChanged.connect(self._update_weights_total)
        self.weight_pmi_spin.valueChanged.connect(self._update_weights_total)
        
        weights_group.setLayout(weights_layout)
        layout.addWidget(weights_group)
        layout.addSpacing(10)
        
        # ====== Trading Rules ======
        rules_group = QGroupBox("Trading Rules")
        rules_layout = QVBoxLayout()
        
        rules_layout.addWidget(QLabel(
            "Minimum gap between strongest and weakest currency to generate a trade signal.\n"
            "If gap < minimum, output 'NO TRADE'. Default: 20 points."
        ))
        
        min_gap_layout = QHBoxLayout()
        min_gap_layout.addWidget(QLabel("Minimum gap to trade:"))
        self.min_gap_spin = QSpinBox()
        self.min_gap_spin.setRange(5, 100)
        self.min_gap_spin.setValue(int(config.MIN_GAP_TO_TRADE))
        self.min_gap_spin.setSuffix(" points")
        min_gap_layout.addWidget(self.min_gap_spin)
        min_gap_layout.addStretch()
        rules_layout.addLayout(min_gap_layout)
        
        rules_group.setLayout(rules_layout)
        layout.addWidget(rules_group)
        layout.addSpacing(10)
        
        # ====== Application Settings ======
        app_group = QGroupBox("Application Settings")
        app_layout = QVBoxLayout()
        
        self.auto_fetch_check = QCheckBox("Auto-fetch interest rates on startup")
        self.auto_fetch_check.setChecked(config.AUTO_FETCH_RATES_ON_STARTUP)
        app_layout.addWidget(self.auto_fetch_check)
        
        app_group.setLayout(app_layout)
        layout.addWidget(app_group)
        layout.addSpacing(15)
        
        # ====== Save Button ======
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        
        save_btn = QPushButton("Save Settings")
        save_btn.setMinimumHeight(42)
        save_btn.clicked.connect(self._save_settings)
        save_layout.addWidget(save_btn)
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("secondary")
        reset_btn.clicked.connect(self._reset_to_defaults)
        save_layout.addWidget(reset_btn)
        
        layout.addLayout(save_layout)
        layout.addStretch()
        
        main_widget.setLayout(layout)
        scroll.setWidget(main_widget)
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
    
    def _load_settings(self):
        """Load settings from .env file."""
        try:
            env_vars = {}
            if self.env_path.exists():
                with open(self.env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            
            # Load API key
            api_key = env_vars.get('FRED_API_KEY', '')
            self.api_key_input.setText(api_key)
            
            mt5_suffix = env_vars.get('MT5_SYMBOL_SUFFIX', '')
            self.mt5_suffix_input.setText(mt5_suffix)
            
            # Load weights (convert from decimal to percentage)
            weight_rate = float(env_vars.get('WEIGHT_RATE', config.WEIGHT_RATE)) * 100
            weight_cpi = float(env_vars.get('WEIGHT_CPI', config.WEIGHT_CPI)) * 100
            weight_pmi = float(env_vars.get('WEIGHT_PMI', config.WEIGHT_PMI)) * 100
            
            self.weight_rate_spin.blockSignals(True)
            self.weight_cpi_spin.blockSignals(True)
            self.weight_pmi_spin.blockSignals(True)
            
            self.weight_rate_spin.setValue(weight_rate)
            self.weight_cpi_spin.setValue(weight_cpi)
            self.weight_pmi_spin.setValue(weight_pmi)
            
            self.weight_rate_spin.blockSignals(False)
            self.weight_cpi_spin.blockSignals(False)
            self.weight_pmi_spin.blockSignals(False)
            
            # Load min gap
            min_gap = float(env_vars.get('MIN_GAP', config.MIN_GAP_TO_TRADE))
            self.min_gap_spin.setValue(int(min_gap))
            
            # Load auto-fetch setting
            auto_fetch = env_vars.get('AUTO_FETCH_RATES_ON_STARTUP', 'true').lower() == 'true'
            self.auto_fetch_check.setChecked(auto_fetch)
            
            self._update_weights_total()
            
        except Exception as e:
            print(f"[ERROR] Failed to load settings: {e}")
    
    def _update_weights_total(self):
        """Update weights total display and color."""
        total = (self.weight_rate_spin.value() + 
                self.weight_cpi_spin.value() + 
                self.weight_pmi_spin.value())
        
        self.weights_total_label.setText(f"Total: {total:.1f}%")
        
        if abs(total - 100) < 0.1:
            self.weights_total_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.weights_total_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
    
    def _test_fred_connection(self):
        """Test FRED API connection in background."""
        api_key = self.api_key_input.text().strip()
        
        if not api_key:
            QMessageBox.warning(self, "Missing API Key", "Please enter a FRED API key first.")
            return
        
        self.test_status.setText("Testing connection...")
        
        self.test_worker = FredTestWorker(api_key)
        self.test_worker.test_complete.connect(self._on_test_complete)
        self.test_worker.start()
    
    def _on_test_complete(self, success: bool, message: str):
        """Handle FRED test completion."""
        self.test_status.setText(message)
        
        if success:
            self.test_status.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.test_status.setStyleSheet("color: #e74c3c; font-weight: bold;")

    def _test_mt5_connection(self):
        """Test MT5 connection in background."""
        suffix = self.mt5_suffix_input.text().strip()
        self.mt5_status_label.setText("Testing connection...")
        self.mt5_status_label.setStyleSheet("color: #95a5a6; font-style: italic;")
        self.mt5_test_worker = Mt5TestWorker(suffix)
        self.mt5_test_worker.test_complete.connect(self._on_mt5_test_complete)
        self.mt5_test_worker.start()

    def _on_mt5_test_complete(self, success: bool, message: str):
        """Handle MT5 test completion."""
        self.mt5_status_label.setText(message)
        if success:
            self.mt5_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.mt5_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

    def _save_settings(self):
        """Save settings to .env file."""
        try:
            # Validate weights sum to 100%
            total = (self.weight_rate_spin.value() + 
                    self.weight_cpi_spin.value() + 
                    self.weight_pmi_spin.value())
            
            if abs(total - 100) > 0.1:
                QMessageBox.warning(
                    self,
                    "Invalid Weights",
                    f"Weights must sum to 100%. Current total: {total:.1f}%"
                )
                return
            
            # Prepare new .env content
            api_key = self.api_key_input.text().strip()
            mt5_suffix = self.mt5_suffix_input.text().strip()
            weight_rate = self.weight_rate_spin.value() / 100
            weight_cpi = self.weight_cpi_spin.value() / 100
            weight_pmi = self.weight_pmi_spin.value() / 100
            min_gap = self.min_gap_spin.value()
            auto_fetch = "true" if self.auto_fetch_check.isChecked() else "false"
            
            env_content = f"""FRED_API_KEY={api_key}
MT5_SYMBOL_SUFFIX={mt5_suffix}
DB_PATH=apex.db
MIN_GAP={min_gap}
WEIGHT_RATE={weight_rate:.2f}
WEIGHT_CPI={weight_cpi:.2f}
WEIGHT_PMI={weight_pmi:.2f}
AUTO_FETCH_RATES_ON_STARTUP={auto_fetch}
DEBUG=false
"""
            
            # Write to .env
            with open(self.env_path, 'w') as f:
                f.write(env_content)
            
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved to .env\nPlease restart the application for changes to take effect."
            )
            
            self.settings_changed.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
    
    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Are you sure? This will reset all settings to factory defaults.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.api_key_input.clear()
            self.mt5_suffix_input.clear()
            self.weight_rate_spin.setValue(50)
            self.weight_cpi_spin.setValue(30)
            self.weight_pmi_spin.setValue(20)
            self.min_gap_spin.setValue(20)
            self.auto_fetch_check.setChecked(True)
