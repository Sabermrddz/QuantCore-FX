"""
APEX Dashboard — Tab 1: Primary View

Top section:  LIVE SIGNAL (intraday, from CurrencyStrengthMatrix Z-scores)
Bottom section: MACRO BACKDROP (monthly, from scorer.py fundamental data)

The live signal is the primary trading reference. Macro Backdrop is slow-moving
context for display only.
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
from currency_strength_matrix import CurrencyStrengthMatrix
from layer2_technical import TechnicalAnalyzer
import scorer


class DashboardTab(QWidget):
    """Dashboard: live intraday signal (CurrencyStrengthMatrix) + macro backdrop (scorer)."""
    
    # Signal to request FRED fetch
    fetch_rates_requested = pyqtSignal()
    
    # Signal emitted when new signal generated (for Layer 2 confluence)
    signal_generated = pyqtSignal(str, str, float, dict)
    
    def __init__(self, db: Database, tech_analyzer: TechnicalAnalyzer = None):
        """
        Initialize Dashboard tab.
        
        Args:
            db: Database instance
            tech_analyzer: TechnicalAnalyzer instance for live signal data
        """
        super().__init__()
        self.db = db
        self.tech_analyzer = tech_analyzer or TechnicalAnalyzer()
        self.matrix = CurrencyStrengthMatrix()
        self.current_month = datetime.now().strftime("%Y-%m")
        self._last_matrix_report = None
        
        self._init_ui()
        self._refresh_display()
    
    def _init_ui(self):
        """Build the UI layout."""
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # ====== Live Signal Card (intraday, from CurrencyStrengthMatrix) ======
        live_card = self._build_live_signal_card()
        layout.addWidget(live_card)
        
        # ====== Macro Backdrop Card (monthly, from scorer.py) ======
        backdrop_card = self._build_macro_backdrop_card()
        layout.addWidget(backdrop_card)
        
        # ====== Ranked Score Table (Macro Backdrop detail) ======
        heading = QLabel("Macro Backdrop — Currency Rankings")
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
    
    def _build_live_signal_card(self) -> QFrame:
        """Build the live intraday signal card (from CurrencyStrengthMatrix)."""
        card = QFrame()
        card.setObjectName("statusCard")

        layout = QVBoxLayout()
        layout.setSpacing(6)

        title = QLabel("LIVE SIGNAL (Intraday)")
        title.setProperty("subheading", True)
        layout.addWidget(title)

        # Matrix Cross pair (largest divergence)
        self.live_signal_label = QLabel("Waiting for Layer 2 data...")
        self.live_signal_label.setProperty("value", True)
        self.live_signal_label.setStyleSheet("color: #2c3e50;")
        layout.addWidget(self.live_signal_label)

        # Divergence gap
        self.live_gap_label = QLabel("Divergence: — σ")
        self.live_gap_label.setStyleSheet("font-size: 15px; color: #5d6d7e;")
        layout.addWidget(self.live_gap_label)

        # Matrix ranked currencies (top/bottom 2)
        self.live_ranked_label = QLabel("")
        self.live_ranked_label.setStyleSheet("font-size: 13px; color: #7f8c8d;")
        layout.addWidget(self.live_ranked_label)

        # Session + SRV
        self.live_session_label = QLabel("Session: —  |  SRV: —")
        self.live_session_label.setStyleSheet("font-size: 12px; color: #95a5a6;")
        layout.addWidget(self.live_session_label)

        # Entry zones (SL/TP text-described, not executable)
        self.live_entry_zones = QLabel("")
        self.live_entry_zones.setStyleSheet("font-size: 12px; color: #8e44ad;")
        layout.addWidget(self.live_entry_zones)

        # Updated timestamp
        self.live_updated_label = QLabel("Updated: —")
        self.live_updated_label.setStyleSheet("color: #95a5a6; font-size: 12px;")
        layout.addWidget(self.live_updated_label)

        layout.addStretch()
        card.setLayout(layout)
        return card

    def _build_macro_backdrop_card(self) -> QFrame:
        """Build the macro backdrop card frame (from scorer.py fundamental data)."""
        card = QFrame()
        card.setObjectName("card")
        
        layout = QVBoxLayout()
        layout.setSpacing(6)
        
        title = QLabel("MACRO BACKDROP (Fundamental — slow context)")
        title.setProperty("subheading", True)
        layout.addWidget(title)
        
        self.macro_signal_label = QLabel("NO TRADE — Initializing...")
        self.macro_signal_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #2c3e50;")
        layout.addWidget(self.macro_signal_label)
        
        self.macro_gap_label = QLabel("Gap: — points")
        self.macro_gap_label.setStyleSheet("font-size: 13px; color: #5d6d7e;")
        layout.addWidget(self.macro_gap_label)
        
        self.macro_updated_label = QLabel("Updated: —")
        self.macro_updated_label.setStyleSheet("color: #95a5a6; font-size: 12px;")
        layout.addWidget(self.macro_updated_label)
        
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
        """Refresh macro backdrop with latest fundamental data."""
        try:
            signal_data = self.db.get_signal(self.current_month)
            
            if signal_data:
                signal_text = signal_data["signal"]
                gap = signal_data["gap"]
                status = signal_data["status"]
                strongest = signal_data.get("strongest")
                weakest = signal_data.get("weakest")

                if strongest and weakest:
                    scores = self.db.get_month_scores(self.current_month)
                    if scores:
                        bias_matrix = scorer.build_directional_bias_matrix(scores)
                    else:
                        bias_matrix = {}
                    self.signal_generated.emit(strongest, weakest, gap, bias_matrix)
                
                self.macro_signal_label.setText(signal_text)
                color = "#27ae60" if status == "ACTIVE" else "#e74c3c"
                self.macro_signal_label.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {color};")
                
                gap_tier = scorer.get_gap_tier(gap)
                tier_name = {
                    "no_trade": "Too narrow",
                    "weak": "Weak signal",
                    "standard": "Standard signal",
                    "strong": "Strong signal"
                }.get(gap_tier, "Unknown")
                
                self.macro_gap_label.setText(f"Gap: {gap:.1f} points · {tier_name}")
            else:
                self.macro_signal_label.setText("NO TRADE — No data yet")
                self.macro_signal_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #e74c3c;")
                self.macro_gap_label.setText("Gap: — points")
            
            self.macro_updated_label.setText(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            self._check_data_staleness()
            self._refresh_score_table()
            
        except Exception as e:
            print(f"[ERROR] Failed to refresh dashboard: {e}")
            self.macro_signal_label.setText("ERROR")
            self.macro_signal_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #e74c3c;")
    
    def _refresh_live_signal(self):
        """Refresh the live intraday signal from CurrencyStrengthMatrix."""
        try:
            z_scores = self.tech_analyzer.get_all_z_scores()
            if not z_scores:
                self.live_signal_label.setText("Waiting for Layer 2 data...")
                self.live_signal_label.setStyleSheet("font-size: 28px; font-weight: 700; color: #95a5a6;")
                self.live_gap_label.setText("Divergence: — σ")
                self.live_ranked_label.setText("")
                self.live_session_label.setText("Session: —  |  SRV: —")
                self.live_entry_zones.setText("")
                return

            current_prices = {}
            for pair in z_scores:
                lp = self.tech_analyzer.get_last_price(pair)
                if lp is not None:
                    current_prices[pair] = lp

            self.matrix.update(z_scores, current_prices=current_prices)
            report = self.matrix.get_report()
            self._last_matrix_report = report

            mc = report.get("matrix_cross")
            gap = report.get("divergence_gap", 0)
            has_div = report.get("has_divergence", False)
            ranked = report.get("ranked", [])

            if mc and mc != "N/A":
                signal_text = mc
                color = "#e74c3c" if has_div else "#2c3e50"
                self.live_signal_label.setText(signal_text)
                self.live_signal_label.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {color};")
                self.live_gap_label.setText(f"Divergence: {gap:.2f}σ{' — EXTREME' if has_div else ''}")
            else:
                self.live_signal_label.setText("No divergence")
                self.live_signal_label.setStyleSheet("font-size: 28px; font-weight: 700; color: #95a5a6;")
                self.live_gap_label.setText("Divergence: — σ")

            if ranked:
                top2 = [f"{c[0]}({c[1]:+.1f}σ)" for c in ranked[:2]]
                bot2 = [f"{c[0]}({c[1]:+.1f}σ)" for c in ranked[-2:]]
                self.live_ranked_label.setText(
                    f"Strongest: {'  '.join(top2)}  |  Weakest: {'  '.join(bot2)}"
                )
            else:
                self.live_ranked_label.setText("")

            session = report.get("active_session", "—")
            srv_data = self.matrix.get_srv_map()
            srv_parts = []
            if srv_data:
                for ccy in ranked[:3]:
                    name = ccy[0]
                    if name in srv_data:
                        s = srv_data[name]
                        sign = "+" if s >= 0 else ""
                        srv_parts.append(f"{name}: {sign}{s:.3f}%")
            srv_str = "  |  ".join(srv_parts)
            self.live_session_label.setText(
                f"Session: {session}  |  SRV: {srv_str}" if srv_str
                else f"Session: {session}  |  SRV: —"
            )

            # Text-described entry zones (advisory only, no position sizing)
            entry_parts = []
            if mc and mc != "N/A":
                entry_price = self.tech_analyzer.get_last_price(mc)
                if entry_price:
                    sl_tp = self.tech_analyzer.calculate_sl_tp(
                        mc, "LONG" if has_div else "SHORT", entry_price
                    )
                    if sl_tp.get("sl") and sl_tp.get("tp"):
                        entry_parts.append(
                            f"Entry zones — {mc}: ~{entry_price:.5f} "
                            f"(SL: {sl_tp['sl']:.5f}, TP: {sl_tp['tp']:.5f})"
                        )
            self.live_entry_zones.setText("  |  ".join(entry_parts))

            self.live_updated_label.setText(
                f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        except Exception as e:
            print(f"[Dashboard] Live signal error: {e}")

    def update_live_signal(self):
        """Called externally to trigger live signal refresh."""
        self._refresh_live_signal()

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
