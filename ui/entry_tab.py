"""
APEX Layer 1 — Tab 2: Monthly Data Entry

This tab allows users to manually enter CPI and PMI data for all 8 currencies
for the current month.

Features:
- Two tables: CPI entry and PMI entry
- Live delta calculation (actual CPI - target)
- Progress bar tracking (X of 16 fields filled)
- Save button disabled until all 16 fields complete
- Month selector dropdown
- Color coding: green for above target, red for below (CPI only)

User flow:
1. Select current month from dropdown
2. Enter 8 CPI values from official releases
3. Enter 8 PMI values from S&P Global
4. Progress bar shows 16/16 when complete
5. Click "Save & Calculate Scores"
6. Triggers scorer.py → updates Dashboard tab
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QProgressBar, QComboBox, QDoubleSpinBox, QHeaderView,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from typing import Dict, Optional
from datetime import datetime, timedelta
import config
from database import Database
import scorer
import pandas as pd
import openpyxl


class MonthlyEntryTab(QWidget):
    """Monthly CPI + PMI data entry form."""
    
    # Signal emitted when data saved successfully
    data_saved = pyqtSignal(str)  # month string
    
    def __init__(self, db: Database):
        """
        Initialize Monthly Entry tab.
        
        Args:
            db: Database instance
        """
        super().__init__()
        self.db = db
        self.current_month = None
        self.cpi_fields = {}  # currency -> QDoubleSpinBox
        self.pmi_fields = {}  # currency -> QDoubleSpinBox
        self.delta_labels = {}  # currency -> QLabel
        self.pmi_signal_labels = {}  # currency -> QLabel
        
        self._init_ui()
        self._connect_signals()
        self._load_current_month()
    
    def _init_ui(self):
        """Build the UI layout."""
        layout = QVBoxLayout()
        
        # ====== Month selector ======
        month_layout = QHBoxLayout()
        month_layout.addWidget(QLabel("Month:"))
        
        self.month_combo = QComboBox()
        self._populate_month_combo()
        month_layout.addWidget(self.month_combo)
        month_layout.addStretch()
        
        layout.addLayout(month_layout)
        layout.addSpacing(10)
        
        # ====== CPI Entry Table ======
        layout.addWidget(QLabel("CPI Entry (Actual YoY % - Enter after each country releases)"))
        
        self.cpi_table = QTableWidget()
        self.cpi_table.setColumnCount(5)
        self.cpi_table.setHorizontalHeaderLabels(
            ["Currency", "Target %", "Actual CPI %", "Delta", "Done"]
        )
        self.cpi_table.setRowCount(len(config.CURRENCIES))
        
        for row, currency in enumerate(config.CURRENCIES):
            # Currency label
            currency_item = QTableWidgetItem(f"{config.CURRENCY_EMOJIS[currency]} {currency}")
            currency_item.setFlags(currency_item.flags() & ~Qt.ItemIsEditable)
            self.cpi_table.setItem(row, 0, currency_item)
            
            # Target
            target = config.CB_TARGETS[currency]
            target_item = QTableWidgetItem(f"{target}%")
            target_item.setFlags(target_item.flags() & ~Qt.ItemIsEditable)
            self.cpi_table.setItem(row, 1, target_item)
            
            # Actual CPI input
            spin = QDoubleSpinBox()
            spin.setRange(config.CPI_MIN, config.CPI_MAX)
            spin.setDecimals(2)
            spin.setValue(0.0)
            spin.setStyleSheet("background-color: white; padding: 2px;")
            self.cpi_fields[currency] = spin
            self.cpi_table.setCellWidget(row, 2, spin)
            
            # Delta label
            delta_label = QLabel("—")
            delta_label.setAlignment(Qt.AlignCenter)
            self.delta_labels[currency] = delta_label
            self.cpi_table.setItem(row, 3, QTableWidgetItem(""))
            self.cpi_table.setCellWidget(row, 3, delta_label)
            
            # Done indicator
            done_item = QTableWidgetItem("○")
            done_item.setTextAlignment(Qt.AlignCenter)
            done_item.setFlags(done_item.flags() & ~Qt.ItemIsEditable)
            self.cpi_table.setItem(row, 4, done_item)
        
        # Auto-resize columns
        self.cpi_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.cpi_table)
        layout.addSpacing(10)
        
        # ====== PMI Entry Table ======
        layout.addWidget(QLabel("PMI Entry (Composite PMI - Enter after S&P Global release)"))
        
        self.pmi_table = QTableWidget()
        self.pmi_table.setColumnCount(5)
        self.pmi_table.setHorizontalHeaderLabels(
            ["Currency", "Neutral", "PMI Reading", "Signal", "Done"]
        )
        self.pmi_table.setRowCount(len(config.CURRENCIES))
        
        for row, currency in enumerate(config.CURRENCIES):
            # Currency label
            currency_item = QTableWidgetItem(f"{config.CURRENCY_EMOJIS[currency]} {currency}")
            currency_item.setFlags(currency_item.flags() & ~Qt.ItemIsEditable)
            self.pmi_table.setItem(row, 0, currency_item)
            
            # Neutral reference
            neutral_item = QTableWidgetItem("50.0")
            neutral_item.setFlags(neutral_item.flags() & ~Qt.ItemIsEditable)
            self.pmi_table.setItem(row, 1, neutral_item)
            
            # PMI input
            spin = QDoubleSpinBox()
            spin.setRange(config.PMI_MIN, config.PMI_MAX)
            spin.setDecimals(1)
            spin.setValue(50.0)  # Default to neutral
            spin.setStyleSheet("background-color: white; padding: 2px;")
            self.pmi_fields[currency] = spin
            self.pmi_table.setCellWidget(row, 2, spin)
            
            # Signal label
            signal_label = QLabel("Neutral")
            signal_label.setAlignment(Qt.AlignCenter)
            self.pmi_signal_labels[currency] = signal_label
            self.pmi_table.setItem(row, 3, QTableWidgetItem(""))
            self.pmi_table.setCellWidget(row, 3, signal_label)
            
            # Done indicator
            done_item = QTableWidgetItem("○")
            done_item.setTextAlignment(Qt.AlignCenter)
            done_item.setFlags(done_item.flags() & ~Qt.ItemIsEditable)
            self.pmi_table.setItem(row, 4, done_item)
        
        self.pmi_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.pmi_table)
        layout.addSpacing(15)
        
        # ====== Progress Bar ======
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Data entry progress:"))
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(16)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v / 16 fields filled")
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        layout.addSpacing(10)
        
        # ====== Buttons ======
        button_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("📊 Import Excel")
        self.import_btn.setMinimumHeight(42)
        button_layout.addWidget(self.import_btn)
        
        button_layout.addStretch()
        
        self.save_btn = QPushButton("Save & Calculate Scores")
        self.save_btn.setObjectName("success")
        self.save_btn.setEnabled(False)
        self.save_btn.setMinimumHeight(42)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def _connect_signals(self):
        """Connect UI signals to slots."""
        # Month selector
        self.month_combo.currentTextChanged.connect(self._on_month_changed)
        
        # CPI field changes
        for currency, spin in self.cpi_fields.items():
            spin.valueChanged.connect(self._on_cpi_changed)
        
        # PMI field changes
        for currency, spin in self.pmi_fields.items():
            spin.valueChanged.connect(self._on_pmi_changed)
        
        # Import button
        self.import_btn.clicked.connect(self._on_import_excel)
        
        # Save button
        self.save_btn.clicked.connect(self._on_save_clicked)
    
    def _populate_month_combo(self):
        """Populate month dropdown with past 24 months + current month."""
        months = []
        today = datetime.now()
        
        # Add current month and past 23 months
        for i in range(24):
            month_date = today - timedelta(days=30 * i)
            month_str = month_date.strftime("%Y-%m")
            months.append(month_str)
        
        self.month_combo.addItems(months)
    
    def _load_current_month(self):
        """Load current month data from database."""
        self.current_month = datetime.now().strftime("%Y-%m")
        
        # Set combo to current month
        current_index = self.month_combo.findText(self.current_month)
        if current_index >= 0:
            self.month_combo.setCurrentIndex(current_index)
        
        self._load_month_data(self.current_month)
    
    def _on_month_changed(self, month_str: str):
        """Handle month selection change."""
        self.current_month = month_str
        self._load_month_data(month_str)
    
    def _load_month_data(self, month: str):
        """Load saved CPI/PMI data from database for a month."""
        try:
            monthly_data = self.db.get_monthly_data(month)
            
            # Clear fields
            for spin in self.cpi_fields.values():
                spin.blockSignals(True)
                spin.setValue(0.0)
                spin.blockSignals(False)
            
            for spin in self.pmi_fields.values():
                spin.blockSignals(True)
                spin.setValue(50.0)
                spin.blockSignals(False)
            
            # Load saved values
            for currency, data in monthly_data.items():
                if data["cpi_actual"] is not None:
                    self.cpi_fields[currency].blockSignals(True)
                    self.cpi_fields[currency].setValue(data["cpi_actual"])
                    self.cpi_fields[currency].blockSignals(False)
                
                if data["pmi_actual"] is not None:
                    self.pmi_fields[currency].blockSignals(True)
                    self.pmi_fields[currency].setValue(data["pmi_actual"])
                    self.pmi_fields[currency].blockSignals(False)
            
            # Refresh UI
            self._update_delta_labels()
            self._update_pmi_signals()
            self._update_progress()
            
        except Exception as e:
            print(f"[ERROR] Failed to load month data: {e}")
    
    def _on_cpi_changed(self):
        """Handle CPI value change."""
        self._update_delta_labels()
        self._update_progress()
    
    def _update_delta_labels(self):
        """Update delta (CPI - target) labels with color coding."""
        for currency, spin in self.cpi_fields.items():
            cpi = spin.value()
            target = config.CB_TARGETS[currency]
            delta = cpi - target
            
            label = self.delta_labels[currency]
            
            if cpi == 0:
                # Not filled
                label.setText("—")
                label.setStyleSheet("")
            else:
                # Show delta with sign
                delta_str = f"{delta:+.2f}%"
                label.setText(delta_str)
                
                # Color code
                if delta > 0:
                    label.setStyleSheet("color: #27ae60; font-weight: bold;")  # Green (hawkish)
                elif delta < 0:
                    label.setStyleSheet("color: #e74c3c; font-weight: bold;")  # Red (dovish)
                else:
                    label.setStyleSheet("color: #95a5a6;")  # Gray (neutral)
    
    def _on_pmi_changed(self):
        """Handle PMI value change."""
        self._update_pmi_signals()
        self._update_progress()
    
    def _update_pmi_signals(self):
        """Update PMI signal labels based on value."""
        for currency, spin in self.pmi_fields.items():
            pmi = spin.value()
            label = self.pmi_signal_labels[currency]
            
            if pmi > 52:
                label.setText("Expanding")
                label.setStyleSheet("color: #27ae60; font-weight: bold;")
            elif pmi >= 50:
                label.setText("Neutral +")
                label.setStyleSheet("color: #f39c12; font-weight: bold;")
            elif pmi > 48:
                label.setText("Neutral −")
                label.setStyleSheet("color: #f39c12; font-weight: bold;")
            else:
                label.setText("Contracting")
                label.setStyleSheet("color: #e74c3c; font-weight: bold;")
    
    def _update_progress(self):
        """Update progress bar and save button state."""
        filled = 0
        
        # Count filled CPI fields
        for currency, spin in self.cpi_fields.items():
            if spin.value() != 0:
                filled += 1
                # Update done indicator
                row = config.CURRENCIES.index(currency)
                self.cpi_table.item(row, 4).setText("✓")
            else:
                row = config.CURRENCIES.index(currency)
                self.cpi_table.item(row, 4).setText("○")
        
        # Count filled PMI fields
        for currency, spin in self.pmi_fields.items():
            if spin.value() != 50.0:  # PMI default is 50 (neutral)
                filled += 1
                # Update done indicator
                row = config.CURRENCIES.index(currency)
                self.pmi_table.item(row, 4).setText("✓")
            else:
                row = config.CURRENCIES.index(currency)
                self.pmi_table.item(row, 4).setText("○")
        
        self.progress_bar.setValue(filled)
        
        # Enable save button only if all 16 fields filled
        self.save_btn.setEnabled(filled == 16)
    
    def _on_import_excel(self):
        """Handle Import Excel button click."""
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Monthly Data from Excel",
            "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            self._load_excel_data(file_path)
            QMessageBox.information(
                self,
                "Success",
                "✓ Data imported successfully!\n\nClick 'Save & Calculate Scores' to process."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import Excel file:\n\n{str(e)}\n\n" +
                "Please check the file format. See EXCEL_IMPORT_PROMPT.md for details."
            )
    
    def _load_excel_data(self, file_path: str):
        """
        Load CPI and PMI data from Excel file.
        
        Expected structure:
        - Sheet 'CPI': Columns [Currency, Target %, Actual CPI %]
        - Sheet 'PMI': Columns [Currency, Composite PMI]
        
        Or single sheet with structure:
        - Columns [Currency, Target_CPI, Actual_CPI, Composite_PMI]
        
        Args:
            file_path: Path to Excel or CSV file
        """
        if file_path.endswith('.csv'):
            # Load from CSV
            df = pd.read_csv(file_path)
            self._parse_csv_data(df)
        else:
            # Load from Excel (try multi-sheet format first, then single-sheet)
            try:
                self._load_excel_multi_sheet(file_path)
            except:
                self._load_excel_single_sheet(file_path)
    
    def _load_excel_multi_sheet(self, file_path: str):
        """Load Excel with separate CPI and PMI sheets."""
        # Load CPI sheet
        cpi_df = pd.read_excel(file_path, sheet_name='CPI')
        pmi_df = pd.read_excel(file_path, sheet_name='PMI')
        
        # Map CPI data
        for _, row in cpi_df.iterrows():
            currency = str(row.iloc[0]).strip().upper()
            if currency in config.CURRENCIES:
                actual_cpi = float(row.iloc[2])
                if actual_cpi != 0:
                    self.cpi_fields[currency].blockSignals(True)
                    self.cpi_fields[currency].setValue(actual_cpi)
                    self.cpi_fields[currency].blockSignals(False)
        
        # Map PMI data
        for _, row in pmi_df.iterrows():
            currency = str(row.iloc[0]).strip().upper()
            if currency in config.CURRENCIES:
                pmi_value = float(row.iloc[1])
                if pmi_value != 0:
                    self.pmi_fields[currency].blockSignals(True)
                    self.pmi_fields[currency].setValue(pmi_value)
                    self.pmi_fields[currency].blockSignals(False)
        
        # Refresh UI
        self._update_delta_labels()
        self._update_pmi_signals()
        self._update_progress()
    
    def _load_excel_single_sheet(self, file_path: str):
        """Load Excel with single sheet containing all data."""
        df = pd.read_excel(file_path)
        self._parse_csv_data(df)
    
    def _parse_csv_data(self, df):
        """Parse DataFrame and populate tables."""
        # Try to detect column names (case-insensitive)
        columns = [str(col).lower().strip() for col in df.columns]
        
        # Map CPI and PMI from dataframe
        for _, row in df.iterrows():
            # Get currency (assume first column or named column)
            currency = str(row.iloc[0]).strip().upper()
            if not currency or currency not in config.CURRENCIES:
                continue
            
            # Try to find CPI column
            cpi_cols = [i for i, c in enumerate(columns) if 'cpi' in c and 'actual' in c]
            if cpi_cols:
                try:
                    actual_cpi = float(row.iloc[cpi_cols[0]])
                    if actual_cpi != 0:
                        self.cpi_fields[currency].blockSignals(True)
                        self.cpi_fields[currency].setValue(actual_cpi)
                        self.cpi_fields[currency].blockSignals(False)
                except (ValueError, IndexError):
                    pass
            
            # Try to find PMI column
            pmi_cols = [i for i, c in enumerate(columns) if 'pmi' in c]
            if pmi_cols:
                try:
                    pmi_value = float(row.iloc[pmi_cols[0]])
                    if pmi_value != 0:
                        self.pmi_fields[currency].blockSignals(True)
                        self.pmi_fields[currency].setValue(pmi_value)
                        self.pmi_fields[currency].blockSignals(False)
                except (ValueError, IndexError):
                    pass
        
        # Refresh UI
        self._update_delta_labels()
        self._update_pmi_signals()
        self._update_progress()
    
    def _on_save_clicked(self):
        """Handle Save & Calculate Scores button click."""
        try:
            # Collect CPI values
            cpi_values = {
                currency: self.cpi_fields[currency].value()
                for currency in config.CURRENCIES
            }
            
            # Collect PMI values
            pmi_values = {
                currency: self.pmi_fields[currency].value()
                for currency in config.CURRENCIES
            }
            
            # Save to database
            for currency in config.CURRENCIES:
                self.db.update_monthly_cpi(self.current_month, currency, cpi_values[currency])
                self.db.update_monthly_pmi(self.current_month, currency, pmi_values[currency])
            
            # Fetch rates from database
            rates = self.db.get_all_rates()
            
            # Score all currencies
            scores = scorer.score_all_currencies(rates, cpi_values, pmi_values)
            
            # Save scores to database
            self.db.save_scores(self.current_month, scores)
            
            # Generate signal
            strongest, weakest, gap = scorer.pair_currencies(scores)
            signal_text, status, gap_desc = scorer.generate_signal(scores)
            
            # Save signal
            self.db.save_signal(
                self.current_month,
                strongest,
                weakest,
                gap,
                signal_text,
                status
            )
            
            # Emit signal so Dashboard tab can refresh
            self.data_saved.emit(self.current_month)
            
            # Show confirmation
            print(f"[Entry] Data saved and scores calculated for {self.current_month}")
            
        except Exception as e:
            print(f"[ERROR] Failed to save data: {e}")
