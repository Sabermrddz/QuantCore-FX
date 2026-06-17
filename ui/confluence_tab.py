"""
APEX Confluence Signals Tab — Layer 1 + Layer 2 Merging

Displays:
- Current Layer 1 fundamental bias
- Layer 2 technical extremes
- Confluence signals (both aligned)
- Risk management details
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QFrame, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QBrush
from typing import Dict, Optional
from datetime import datetime
import config
from layer2_technical import TechnicalAnalyzer
from confluence_filter import ConfluenceFilter, SignalHistory
from risk_management import RiskManagementSystem
from database import Database


class ConfluenceSignalsTab(QWidget):
    """Confluence signals monitoring and execution."""
    
    def __init__(self, db: Database, tech_analyzer: TechnicalAnalyzer):
        super().__init__()
        
        self.db = db
        self.tech_analyzer = tech_analyzer
        self.confluence = ConfluenceFilter(tech_analyzer)
        self.risk_mgmt = RiskManagementSystem(account_balance=config.ACCOUNT_BALANCE)
        self.signal_history = SignalHistory()
        
        self._init_ui()
        self._setup_auto_refresh()
    
    def _init_ui(self):
        """Build UI layout."""
        layout = QVBoxLayout()
        
        # ====== Confluence Status Card ======
        card = self._build_status_card()
        layout.addWidget(card)
        layout.addSpacing(15)
        
        # ====== Active Signals Table ======
        layout.addWidget(QLabel("Confluence Signals (Layer 1 + Layer 2)"))
        
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(8)
        self.signals_table.setHorizontalHeaderLabels([
            "Pair", "L1 Gap", "L2 Z-Score", "Status", "Confidence", "Entry Price", "Position Size", "Action"
        ])
        self.signals_table.setRowCount(10)
        
        layout.addWidget(self.signals_table)
        layout.addSpacing(15)
        
        # ====== Risk Management Panel ======
        risk_layout = QHBoxLayout()
        risk_layout.addWidget(QLabel("Portfolio Exposure:"))
        
        self.exposure_bar = QProgressBar()
        self.exposure_bar.setMaximum(100)
        risk_layout.addWidget(self.exposure_bar)
        
        self.leverage_label = QLabel("Leverage: —")
        risk_layout.addWidget(self.leverage_label)
        
        layout.addLayout(risk_layout)
        layout.addSpacing(10)
        
        # ====== Control Buttons ======
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh Signals")
        refresh_btn.clicked.connect(self._refresh_signals)
        button_layout.addWidget(refresh_btn)
        
        execute_btn = QPushButton("Execute Top Signal")
        execute_btn.clicked.connect(self._execute_signal)
        button_layout.addWidget(execute_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def _build_status_card(self) -> QFrame:
        """Build confluence status card."""
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
        
        title = QLabel("CONFLUENCE STATUS")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(title)
        layout.addSpacing(5)
        
        # Layer 1 status
        layer1_layout = QHBoxLayout()
        layer1_layout.addWidget(QLabel("Layer 1 (Fundamental):"))
        self.layer1_status_label = QLabel("No bias")
        self.layer1_status_label.setFont(QFont("Arial", 11, QFont.Bold))
        layer1_layout.addWidget(self.layer1_status_label)
        layer1_layout.addStretch()
        layout.addLayout(layer1_layout)

        # Directional Bias Matrix display
        bias_layout = QHBoxLayout()
        bias_layout.addWidget(QLabel("Macro Boundaries:"))
        self.bias_matrix_label = QLabel("No bias matrix")
        self.bias_matrix_label.setStyleSheet("color: #8e44ad; font-size: 10px;")
        bias_layout.addWidget(self.bias_matrix_label)
        bias_layout.addStretch()
        layout.addLayout(bias_layout)
        
        # Layer 2 status
        layer2_layout = QHBoxLayout()
        layer2_layout.addWidget(QLabel("Layer 2 (Technical):"))
        self.layer2_status_label = QLabel("No extreme")
        self.layer2_status_label.setStyleSheet("color: #95a5a6;")
        layer2_layout.addWidget(self.layer2_status_label)
        layer2_layout.addStretch()
        layout.addLayout(layer2_layout)
        
        # Confluence result
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Confluence Result:"))
        self.confluence_status_label = QLabel("❌ NO CONFLUENCE")
        self.confluence_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.confluence_status_label.setFont(QFont("Arial", 12, QFont.Bold))
        conf_layout.addWidget(self.confluence_status_label)
        conf_layout.addStretch()
        layout.addLayout(conf_layout)

        # Matrix cross (S.A.T.O.R.I.)
        matrix_layout = QHBoxLayout()
        matrix_layout.addWidget(QLabel("Matrix Cross:"))
        self.matrix_cross_label = QLabel("—")
        self.matrix_cross_label.setStyleSheet("font-weight: bold; color: #8e44ad;")
        matrix_layout.addWidget(self.matrix_cross_label)
        matrix_layout.addStretch()
        layout.addLayout(matrix_layout)

        self.matrix_detail_label = QLabel("")
        self.matrix_detail_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        layout.addWidget(self.matrix_detail_label)

        card.setLayout(layout)
        return card
    
    def set_layer1_signal(self, strongest: str, weakest: str, gap: float,
                           bias_matrix: dict = None):
        """Update Layer 1 directional bias matrix from Dashboard."""
        self.confluence.set_layer1_bias(strongest, weakest, gap, bias_matrix)
        self._refresh_signals()
    
    def _refresh_signals(self):
        """Refresh confluence signal display."""
        try:
            report = self.confluence.get_confluence_report()

            # Update bias matrix display
            bias = report.get("bias_matrix", {})
            if bias:
                parts = []
                for ccy in config.CURRENCIES:
                    d = bias.get(ccy, "—")
                    if d == "STRONG":
                        parts.append(f"{ccy}↑")
                    elif d == "WEAK":
                        parts.append(f"{ccy}↓")
                    else:
                        parts.append(f"{ccy}—")
                self.bias_matrix_label.setText("  ".join(parts))
                self.bias_matrix_label.setStyleSheet("color: #8e44ad; font-size: 10px;")
            else:
                self.bias_matrix_label.setText("No bias matrix")
                self.bias_matrix_label.setStyleSheet("color: #95a5a6; font-size: 10px;")

            # Update matrix cross display
            mc = report.get("matrix_cross", "—")
            gap = report.get("divergence_gap", 0)
            has_div = report.get("has_matrix_divergence", False)
            ranked = report.get("matrix_ranked", [])

            if mc and mc != "N/A":
                self.matrix_cross_label.setText(f"{mc} (spread: {gap:.2f}σ)")
                if has_div:
                    self.matrix_cross_label.setStyleSheet("font-weight: bold; color: #e74c3c;")
                else:
                    self.matrix_cross_label.setStyleSheet("font-weight: bold; color: #8e44ad;")
            else:
                self.matrix_cross_label.setText("—")
                self.matrix_cross_label.setStyleSheet("font-weight: bold; color: #95a5a6;")

            if ranked:
                top3 = [f"{c[0]}({c[1]:+.1f})" for c in ranked[:3]]
                bot3 = [f"{c[0]}({c[1]:+.1f})" for c in ranked[-3:]]
                self.matrix_detail_label.setText(
                    f"Strongest → {' | '.join(top3)}  —  Weakest → {' | '.join(bot3)}"
                )
            else:
                self.matrix_detail_label.setText("")

            # Check for confluence
            should_enter, reason, strength = self.confluence.check_entry_confluence()

            # Update status
            if should_enter:
                l1s = self.confluence.layer1_strongest or "—"
                l1w = self.confluence.layer1_weakest or "—"
                self.layer1_status_label.setText(f"🟢 {l1s}/{l1w} (Gap: {self.confluence.layer1_gap:.1f})")

                pair = f"{self.confluence.layer1_strongest}_{self.confluence.layer1_weakest}" if self.confluence.layer1_strongest else "—"
                z_score = self.tech_analyzer.get_z_score(pair) if pair != "—" else 0
                self.layer2_status_label.setText(f"🔴 {pair} Z-score: {z_score:.2f}")
                self.layer2_status_label.setStyleSheet("color: #27ae60;")

                if has_div:
                    self.confluence_status_label.setText(f"✅ MATRIX DIVERGENCE: {strength:.0f}%")
                else:
                    self.confluence_status_label.setText(f"✅ CONFLUENCE: {strength:.0f}% confidence")
                self.confluence_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")

                self._populate_signal_table(strength)
            else:
                self.layer1_status_label.setText("No signal")
                self.layer2_status_label.setText("No extreme")
                self.layer2_status_label.setStyleSheet("color: #95a5a6;")

                self.confluence_status_label.setText("❌ NO CONFLUENCE")
                self.confluence_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

            # Update risk metrics
            portfolio = self.risk_mgmt.get_portfolio_summary()
            exposure_pct = min((portfolio['total_exposure'] / config.ACCOUNT_BALANCE) * 100, 100)
            self.exposure_bar.setValue(int(exposure_pct))
            self.leverage_label.setText(f"Leverage: {portfolio['leverage_ratio']:.2f}x")

        except Exception as e:
            print(f"[Confluence] Error refreshing: {e}")
    
    def _populate_signal_table(self, confluence_strength: float):
        """Populate the signals table with matrix and confluence data."""
        report = self.confluence.get_confluence_report()
        signals = self.confluence.get_all_signals()

        self.signals_table.clearContents()
        row = 0

        for pair_key, signal in signals.items():
            if row >= self.signals_table.rowCount():
                break

            pair_item = QTableWidgetItem(pair_key)
            pair_item.setFlags(pair_item.flags() & ~Qt.ItemIsEditable)
            if signal.get('type') == 'MATRIX_DIVERGENCE':
                pair_item.setForeground(QColor("#8e44ad"))
            self.signals_table.setItem(row, 0, pair_item)

            # L1 Gap (from report)
            gap_item = QTableWidgetItem(f"{report.get('layer1_gap', 0):.1f}")
            gap_item.setFlags(gap_item.flags() & ~Qt.ItemIsEditable)
            self.signals_table.setItem(row, 1, gap_item)

            # L2 Z-Score
            z = report.get('layer2_z_score', 0)
            if signal.get('type') == 'MATRIX_DIVERGENCE':
                z = report.get('matrix_cross_z', 0)
            z_item = QTableWidgetItem(f"{z:.2f}")
            z_item.setFlags(z_item.flags() & ~Qt.ItemIsEditable)
            self.signals_table.setItem(row, 2, z_item)

            # Status
            sig_type = signal.get('type', 'SIGNAL').replace('_', ' ')
            status_item = QTableWidgetItem(sig_type)
            if 'DIVERGENCE' in sig_type:
                status_item.setBackground(QColor("#f3e5f5"))
                status_item.setForeground(QColor("#6a1b9a"))
            else:
                status_item.setBackground(QColor("#e8f5e9"))
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.signals_table.setItem(row, 3, status_item)

            # Confidence
            strength = signal.get('strength', confluence_strength)
            conf_item = QTableWidgetItem(f"{strength:.0f}%")
            conf_item.setFont(QFont("Arial", 10, QFont.Bold))
            conf_item.setFlags(conf_item.flags() & ~Qt.ItemIsEditable)
            self.signals_table.setItem(row, 4, conf_item)

            row += 1
    
    def _execute_signal(self):
        """Execute the top confluence signal."""
        signals = self.confluence.get_all_signals()
        if not signals:
            QMessageBox.warning(self, "No Signal", "No valid confluence signal to execute")
            return

        try:
            best = max(signals.values(), key=lambda s: s.get('strength', 0))
            pair = best['pair']
            strength = best['strength']

            current_price = 1.0

            trade = self.risk_mgmt.execute_signal(
                pair,
                strength,
                current_price,
                use_hedging=config.USE_GRID_HEDGING
            )
            
            if trade:
                msg = (
                    f"Trade Executed:\n"
                    f"Pair: {trade['pair']}\n"
                    f"Entry: {trade['entry_price']:.4f}\n"
                    f"Size: {trade['position_size']:.2f} lots\n"
                    f"Confidence: {trade['confluence_strength']:.0f}%"
                )
                QMessageBox.information(self, "Trade Executed", msg)
                
                self.signal_history.add_signal({
                    'pair': pair,
                    'type': best.get('type', 'SIGNAL'),
                    'entry_price': current_price,
                    'confluence_strength': strength,
                })
            else:
                QMessageBox.warning(
                    self,
                    "Execution Failed",
                    "Position size would exceed portfolio leverage limits"
                )
            
            self._refresh_signals()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Execution failed: {e}")
    
    def _setup_auto_refresh(self):
        """Setup automatic refresh timer."""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_signals)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
