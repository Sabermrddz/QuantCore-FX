"""
APEX Layer 1 — Tab 3: History

Displays past trading signals and monthly scores.

Features:
- Table with past months (newest first)
- Columns: Month, Signal, Gap, Strongest, Weakest, Status
- Click any row to expand and see full score breakdown for all 8 currencies
- Sort by month/gap/status
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
import config
from database import Database


class HistoryTab(QWidget):
    """History tab showing past signals and scores."""
    
    def __init__(self, db: Database):
        """
        Initialize History tab.
        
        Args:
            db: Database instance
        """
        super().__init__()
        self.db = db
        
        self._init_ui()
        self._load_history()
    
    def _init_ui(self):
        """Build the UI layout."""
        layout = QVBoxLayout()
        
        heading = QLabel("Signal History (Past 24 Months)")
        heading.setProperty("heading", True)
        layout.addWidget(heading)
        
        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Month", "Signal", "Gap", "Strongest", "Weakest", "Status"
        ])
        
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SingleSelection)
        self.history_table.itemClicked.connect(self._on_row_clicked)
        
        layout.addWidget(self.history_table)
        self.setLayout(layout)
    
    def _load_history(self):
        """Load signal history from database."""
        try:
            signals = self.db.get_all_signals(limit=24)
            
            if not signals:
                self.history_table.setRowCount(0)
                return
            
            self.history_table.setRowCount(len(signals))
            
            for row, signal_data in enumerate(signals):
                month = signal_data["month"]
                signal_text = signal_data["signal"]
                gap = signal_data["gap"]
                strongest = signal_data["strongest"]
                weakest = signal_data["weakest"]
                status = signal_data["status"]
                
                # Month
                month_item = QTableWidgetItem(month)
                month_item.setFlags(month_item.flags() & ~Qt.ItemIsEditable)
                self.history_table.setItem(row, 0, month_item)
                
                # Signal
                signal_item = QTableWidgetItem(signal_text)
                signal_item.setFlags(signal_item.flags() & ~Qt.ItemIsEditable)
                self.history_table.setItem(row, 1, signal_item)
                
                # Gap
                gap_item = QTableWidgetItem(f"{gap:.1f}")
                gap_item.setFlags(gap_item.flags() & ~Qt.ItemIsEditable)
                gap_item.setTextAlignment(Qt.AlignCenter)
                self.history_table.setItem(row, 2, gap_item)
                
                # Strongest
                strongest_item = QTableWidgetItem(f"{config.CURRENCY_EMOJIS.get(strongest, '')} {strongest}")
                strongest_item.setFlags(strongest_item.flags() & ~Qt.ItemIsEditable)
                self.history_table.setItem(row, 3, strongest_item)
                
                # Weakest
                weakest_item = QTableWidgetItem(f"{config.CURRENCY_EMOJIS.get(weakest, '')} {weakest}")
                weakest_item.setFlags(weakest_item.flags() & ~Qt.ItemIsEditable)
                self.history_table.setItem(row, 4, weakest_item)
                
                # Status
                status_item = QTableWidgetItem(status)
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
                status_item.setTextAlignment(Qt.AlignCenter)
                
                # Color code status
                if status == "ACTIVE":
                    status_item.setForeground(QColor("#27ae60"))
                    status_item.setFont(QFont("Arial", 10, QFont.Bold))
                elif status == "NO_TRADE":
                    status_item.setForeground(QColor("#e74c3c"))
                else:
                    status_item.setForeground(QColor("#95a5a6"))
                
                self.history_table.setItem(row, 5, status_item)
            
            self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            
        except Exception as e:
            print(f"[ERROR] Failed to load history: {e}")
    
    def _on_row_clicked(self, item: QTableWidgetItem):
        """Handle row click to show detailed score breakdown."""
        row = item.row()
        month = self.history_table.item(row, 0).text()
        
        try:
            # Get scores for this month
            scores = self.db.get_month_scores(month)
            
            if not scores:
                QMessageBox.information(
                    self,
                    "No Scores",
                    f"No score data found for {month}"
                )
                return
            
            # Build detailed breakdown
            breakdown_lines = [f"Score Breakdown for {month}:", ""]
            
            # Get ranked list
            ranked = sorted(
                [(c, s) for c, s in scores.items()],
                key=lambda x: x[1]['rank']
            )
            
            for currency, score_data in ranked:
                rank = score_data['rank']
                score_rate = score_data.get('score_rate', 0)
                score_cpi = score_data.get('score_cpi', 0)
                score_pmi = score_data.get('score_pmi', 0)
                total = score_data['total_score']
                
                breakdown_lines.append(
                    f"{rank}. {config.CURRENCY_EMOJIS.get(currency, '')} {currency:>3} | "
                    f"Total: {total:>5.1f} | "
                    f"Rate: {score_rate:>5.1f} CPI: {score_cpi:>5.1f} PMI: {score_pmi:>5.1f}"
                )
            
            breakdown_text = "\n".join(breakdown_lines)
            
            QMessageBox.information(
                self,
                f"Score Details — {month}",
                breakdown_text
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load score details: {e}"
            )
    
    def refresh_history(self):
        """Refresh history display (called when new data saved)."""
        self._load_history()
