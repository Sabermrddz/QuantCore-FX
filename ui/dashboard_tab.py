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
    QFrame, QPushButton, QSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QFont, QBrush, QPixmap
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
        
        # ====== Signal Card ======
        signal_card = self._build_signal_card()
        layout.addWidget(signal_card)
        layout.addSpacing(15)
        
        # ====== Ranked Score Table ======
        layout.addWidget(QLabel("Currency Rankings"))
        
        self.score_table = QTableWidget()
        self.score_table.setColumnCount(8)
        self.score_table.setHorizontalHeaderLabels([
            "Rank", "Currency", "Rate (%)", "CPI (%)", "PMI", "Score", "Signal", "Strength"
        ])
        self.score_table.setRowCount(len(config.CURRENCIES))
        self.score_table.setAlternatingRowColors(True)
        self.score_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.score_table.setSelectionMode(QTableWidget.SingleSelection)
        
        # Pre-fill with placeholder rows
        for row in range(len(config.CURRENCIES)):
            for col in range(8):
                item = QTableWidgetItem("—")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.score_table.setItem(row, col, item)
        
        self.score_table.resizeColumnsToContents()
        layout.addWidget(self.score_table)
        layout.addSpacing(15)
        
        # ====== Refresh Button ======
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh")
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
        card.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("PRIMARY SIGNAL")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        title.setStyleSheet("color: #495057;")
        layout.addWidget(title)
        layout.addSpacing(5)
        
        # Signal text (large, bold)
        self.signal_label = QLabel("NO TRADE — Initializing...")
        self.signal_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.signal_label.setStyleSheet("color: #2c3e50;")
        layout.addWidget(self.signal_label)
        layout.addSpacing(10)
        
        # Gap and status
        self.gap_label = QLabel("Gap: — points")
        self.gap_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.gap_label)
        
        # Updated timestamp
        self.updated_label = QLabel("Updated: —")
        self.updated_label.setFont(QFont("Arial", 10))
        self.updated_label.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(self.updated_label)
        
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
                
                # Update signal label
                self.signal_label.setText(signal_text)
                
                # Color code based on status
                if status == "ACTIVE":
                    self.signal_label.setStyleSheet("color: #27ae60;")  # Green
                else:
                    self.signal_label.setStyleSheet("color: #e74c3c;")  # Red
                
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
            
            # Refresh score table
            self._refresh_score_table()
            
        except Exception as e:
            print(f"[ERROR] Failed to refresh dashboard: {e}")
            self.signal_label.setText("ERROR")
            self.signal_label.setStyleSheet("color: #e74c3c;")
    
    def _refresh_score_table(self):
        """Refresh the ranked currency table."""
        try:
            scores = self.db.get_month_scores(self.current_month)
            
            if not scores:
                # No scores yet
                for row in range(len(config.CURRENCIES)):
                    for col in range(8):
                        self.score_table.item(row, col).setText("—")
                return
            
            # Get sorted list
            ranked = [(c, s) for c, s in sorted(
                scores.items(),
                key=lambda x: x[1]['rank']
            )]
            
            # Get rates for display
            rates = self.db.get_all_rates()
            
            # Get monthly data for CPI display
            monthly_data = self.db.get_monthly_data(self.current_month)
            
            for row, (currency, score_data) in enumerate(ranked):
                rank = score_data['rank']
                total_score = score_data['total_score']
                rate = rates.get(currency)
                cpi_data = monthly_data.get(currency, {})
                cpi = cpi_data.get('cpi_actual')
                pmi = cpi_data.get('pmi_actual')
                
                # Rank
                self.score_table.item(row, 0).setText(str(rank))
                
                # Currency
                currency_text = f"{config.CURRENCY_EMOJIS.get(currency, '')} {currency}"
                self.score_table.item(row, 1).setText(currency_text)
                
                # Rate
                rate_text = f"{rate:.2f}" if rate is not None else "—"
                self.score_table.item(row, 2).setText(rate_text)
                
                # CPI
                cpi_text = f"{cpi:.2f}" if cpi is not None else "—"
                self.score_table.item(row, 3).setText(cpi_text)
                
                # PMI
                pmi_text = f"{pmi:.1f}" if pmi is not None else "—"
                self.score_table.item(row, 4).setText(pmi_text)
                
                # Score (two decimals)
                self.score_table.item(row, 5).setText(f"{total_score:.1f}")
                
                # Signal tag (BUY for strongest, SELL for weakest)
                if rank == 1:
                    self.score_table.item(row, 6).setText("BUY")
                elif rank == len(config.CURRENCIES):
                    self.score_table.item(row, 6).setText("SELL")
                else:
                    self.score_table.item(row, 6).setText("")
                
                # Strength bar (visual progress 0-100)
                strength_item = self.score_table.item(row, 7)
                strength_item.setText(f"{int(total_score)}%")
                
                # Color code rows
                if rank == 1:
                    # Strongest = GREEN
                    for col in range(8):
                        self.score_table.item(row, col).setBackground(QColor("#d5f4e6"))
                        self.score_table.item(row, col).setForeground(QColor("#27ae60"))
                        self.score_table.item(row, col).setFont(QFont("Arial", 10, QFont.Bold))
                
                elif rank == len(config.CURRENCIES):
                    # Weakest = RED
                    for col in range(8):
                        self.score_table.item(row, col).setBackground(QColor("#fadbd8"))
                        self.score_table.item(row, col).setForeground(QColor("#e74c3c"))
                        self.score_table.item(row, col).setFont(QFont("Arial", 10, QFont.Bold))
                
                else:
                    # Middle = neutral
                    for col in range(8):
                        self.score_table.item(row, col).setBackground(QColor("#ffffff"))
                        self.score_table.item(row, col).setForeground(QColor("#2c3e50"))
                        self.score_table.item(row, col).setFont(QFont("Arial", 10))
            
            # Auto-resize columns to content
            self.score_table.resizeColumnsToContents()
            
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
