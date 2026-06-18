"""
APEX Layer 1 — Tab 1: Dashboard

This is the main screen the user sees every day.

Features:
- Signal card at top (shows PRIMARY SIGNAL, gap, status, updated date)
- Ranked score table below with all 8 currencies
- Strongest row highlighted GREEN (BUY)
- Weakest row highlighted RED (SELL)
- Score bar charts per row (visual progress)
- Auto-refresh when data updated from Entry tab or FRED API

Display:
- Rank, Currency, Rate, CPI, PMI, Score columns
- Color-coded rows, "BUY" and "SELL" tags
- Last updated timestamp
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QFrame, QPushButton, QProgressBar, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from typing import Dict, Optional
from datetime import datetime
import config
from database import Database
import scorer


class DashboardTab(QWidget):
    """Main dashboard showing current signal and currency rankings."""
    
    # Signal to request FRED fetch
    fetch_rates_requested = pyqtSignal()
    
    # Signal emitted when new signal generated (for Layer 2 confluence)
    # Emits: strongest, weakest, gap, directional_bias_matrix
    signal_generated = pyqtSignal(str, str, float, dict)
    
    def __init__(self, db: Database):
        """
        Initialize Dashboard tab.
        
        Args:
            db: Database instance
        """
        super().__init__()
        self.db = db
        self.current_month = datetime.now().strftime("%Y-%m")
        
        self._init_ui()
        self._refresh_display()
    
    def _init_ui(self):
        """Build the UI layout."""
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # ====== Signal Card ======
        signal_card = self._build_signal_card()
        layout.addWidget(signal_card)
        
        # ====== Ranked Score Table ======
        heading = QLabel("Currency Rankings")
        heading.setProperty("heading", True)
        layout.addWidget(heading)
        
        self.score_table = QTableWidget()
        self.score_table.setColumnCount(8)
        self.score_table.setHorizontalHeaderLabels([
            "Rank", "Currency", "Rate (%)", "CPI (%)", "PMI", "Score", "Signal", "Strength"
        ])
        self.score_table.setRowCount(len(config.CURRENCIES))
        self.score_table.setAlternatingRowColors(True)
        self.score_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.score_table.setSelectionMode(QTableWidget.SingleSelection)
        
        # Store progress bars for strength column (column 7)
        self.strength_bars = {}
        
        # Pre-fill with placeholder rows
        for row in range(len(config.CURRENCIES)):
            for col in range(8):
                item = QTableWidgetItem("—")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.score_table.setItem(row, col, item)
            # Add progress bar for strength column
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(True)
            bar.setFormat("")
            self.score_table.setCellWidget(row, 7, bar)
            self.strength_bars[row] = bar
        
        for col in range(7):
            self.score_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        self.score_table.setColumnWidth(7, 140)
        layout.addWidget(self.score_table)
        
        # ====== Refresh Button ======
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("secondary")
        self.refresh_btn.clicked.connect(self._refresh_display)
        button_layout.addWidget(self.refresh_btn)
        
        fetch_btn = QPushButton("Fetch Rates (FRED)")
        fetch_btn.clicked.connect(self._on_fetch_rates)
        button_layout.addWidget(fetch_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def _build_signal_card(self) -> QFrame:
        """Build the signal card frame."""
        card = QFrame()
        card.setObjectName("statusCard")
        
        layout = QVBoxLayout()
        layout.setSpacing(6)
        
        # Title
        title = QLabel("PRIMARY SIGNAL")
        title.setProperty("subheading", True)
        layout.addWidget(title)
        
        # Signal text (large, bold)
        self.signal_label = QLabel("NO TRADE — Initializing...")
        self.signal_label.setProperty("value", True)
        self.signal_label.setStyleSheet("color: #2c3e50;")
        layout.addWidget(self.signal_label)
        
        # Gap and status
        self.gap_label = QLabel("Gap: — points")
        self.gap_label.setStyleSheet("font-size: 15px; color: #5d6d7e;")
        layout.addWidget(self.gap_label)
        
        # Updated timestamp
        self.updated_label = QLabel("Updated: —")
        self.updated_label.setStyleSheet("color: #95a5a6; font-size: 12px;")
        layout.addWidget(self.updated_label)
        
        # Staleness warning (hidden by default)
        self.stale_warning = QLabel("")
        self.stale_warning.setStyleSheet(
            "color: #e74c3c; font-weight: 700; font-size: 13px; padding: 6px 0;"
        )
        self.stale_warning.hide()
        layout.addWidget(self.stale_warning)
        
        layout.addStretch()
        card.setLayout(layout)
        return card
    
    def _refresh_display(self):
        """Refresh dashboard with latest data."""
        try:
            # Get signal for current month
            signal_data = self.db.get_signal(self.current_month)
            
            if signal_data:
                signal_text = signal_data["signal"]
                gap = signal_data["gap"]
                status = signal_data["status"]
                strongest = signal_data.get("strongest")
                weakest = signal_data.get("weakest")

                # Build directional bias matrix and emit to confluence tab
                if strongest and weakest:
                    scores = self.db.get_month_scores(self.current_month)
                    if scores:
                        bias_matrix = scorer.build_directional_bias_matrix(scores)
                    else:
                        bias_matrix = {}
                    self.signal_generated.emit(strongest, weakest, gap, bias_matrix)
                
                self.signal_label.setText(signal_text)
                if status == "ACTIVE":
                    self.signal_label.setStyleSheet("color: #27ae60;")
                else:
                    self.signal_label.setStyleSheet("color: #e74c3c;")
                
                # Update gap label
                gap_tier = scorer.get_gap_tier(gap)
                tier_name = {
                    "no_trade": "Too narrow",
                    "weak": "Weak signal",
                    "standard": "Standard signal",
                    "strong": "Strong signal"
                }.get(gap_tier, "Unknown")
                
                self.gap_label.setText(f"Gap: {gap:.1f} points · {tier_name}")
            else:
                self.signal_label.setText("NO TRADE — No data yet")
                self.signal_label.setStyleSheet("color: #e74c3c;")
                self.gap_label.setText("Gap: — points")
            
            # Update timestamp
            self.updated_label.setText(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Check for stale CPI/PMI data
            self._check_data_staleness()
            
            # Refresh score table
            self._refresh_score_table()
            
        except Exception as e:
            print(f"[ERROR] Failed to refresh dashboard: {e}")
            self.signal_label.setText("ERROR")
            self.signal_label.setStyleSheet("color: #e74c3c;")
    
    def _check_data_staleness(self):
        """Show a warning if CPI/PMI data is older than 35 days."""
        try:
            monthly = self.db.get_monthly_data(self.current_month)
            if not monthly:
                return
            timestamps = []
            for ccy, data in monthly.items():
                ts = data.get("entered_at")
                if ts:
                    timestamps.append(ts)
            if not timestamps:
                return
            latest = max(timestamps)
            try:
                latest_dt = datetime.strptime(latest.split(".")[0], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                latest_dt = datetime.strptime(latest[:10], "%Y-%m-%d")
            days_old = (datetime.now() - latest_dt).days
            if days_old > 35:
                self.stale_warning.setText(
                    f"⚠ CPI/PMI data is {days_old} days old — refresh fundamental data"
                )
                self.stale_warning.show()
            else:
                self.stale_warning.hide()
        except Exception:
            self.stale_warning.hide()

    def _refresh_score_table(self):
        """Refresh the ranked currency table."""
        try:
            scores = self.db.get_month_scores(self.current_month)
            
            if not scores:
                for row in range(len(config.CURRENCIES)):
                    for col in range(8):
                        self.score_table.item(row, col).setText("—")
                    self.strength_bars[row].setValue(0)
                    self.strength_bars[row].setFormat("")
                return
            
            ranked = [(c, s) for c, s in sorted(
                scores.items(),
                key=lambda x: x[1]['rank']
            )]
            
            rates = self.db.get_all_rates()
            monthly_data = self.db.get_monthly_data(self.current_month)
            
            for row, (currency, score_data) in enumerate(ranked):
                rank = score_data['rank']
                total_score = score_data['total_score']
                rate = rates.get(currency)
                cpi_data = monthly_data.get(currency, {})
                cpi = cpi_data.get('cpi_actual')
                pmi = cpi_data.get('pmi_actual')
                
                self.score_table.item(row, 0).setText(str(rank))
                currency_text = f"{config.CURRENCY_EMOJIS.get(currency, '')} {currency}"
                self.score_table.item(row, 1).setText(currency_text)
                self.score_table.item(row, 2).setText(f"{rate:.2f}" if rate is not None else "—")
                self.score_table.item(row, 3).setText(f"{cpi:.2f}" if cpi is not None else "—")
                self.score_table.item(row, 4).setText(f"{pmi:.1f}" if pmi is not None else "—")
                self.score_table.item(row, 5).setText(f"{total_score:.1f}")
                
                # Signal tag
                if rank == 1:
                    self.score_table.item(row, 6).setText("BUY")
                elif rank == len(config.CURRENCIES):
                    self.score_table.item(row, 6).setText("SELL")
                else:
                    self.score_table.item(row, 6).setText("")
                
                # Strength progress bar
                bar = self.strength_bars[row]
                score_int = min(int(total_score), 100)
                bar.setValue(score_int)
                bar.setFormat(f"{score_int}%")
                bar.setStyleSheet(
                    "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                    "stop:0 #2ecc71, stop:1 #27ae60); border-radius: 4px; }"
                    if rank == 1 else
                    "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                    "stop:0 #e74c3c, stop:1 #c0392b); border-radius: 4px; }"
                    if rank == len(config.CURRENCIES) else
                    ""
                )
                
                # Row color coding
                bg = QColor("#d5f4e6") if rank == 1 else QColor("#fadbd8") if rank == len(config.CURRENCIES) else QColor("#ffffff")
                fg = QColor("#1e8449") if rank == 1 else QColor("#c0392b") if rank == len(config.CURRENCIES) else QColor("#2c3e50")
                font = QFont("Segoe UI", 11, QFont.Bold) if rank in (1, len(config.CURRENCIES)) else QFont("Segoe UI", 11)
                
                for col in range(7):
                    self.score_table.item(row, col).setBackground(bg)
                    self.score_table.item(row, col).setForeground(fg)
                    self.score_table.item(row, col).setFont(font)
            
        except Exception as e:
            print(f"[ERROR] Failed to refresh score table: {e}")
    
    def _on_fetch_rates(self):
        """Handle fetch rates button click."""
        self.fetch_rates_requested.emit()
    
    def on_data_saved(self, month: str):
        """
        Called when entry tab saves new data.
        
        Args:
            month: Month string (YYYY-MM)
        """
        self.current_month = month
        self._refresh_display()
    
    def on_rates_updated(self, rates: Dict[str, float]):
        """
        Called when FRED rates fetched successfully.
        
        Args:
            rates: Dict mapping currency to rate
        """
        # Rates are saved to DB by the thread, just refresh display
        self._refresh_display()
