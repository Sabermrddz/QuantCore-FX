"""
APEX Confluence Signals Tab — Layer 1 + Layer 2 Merging

DISPLAY ONLY — no position sizing, no auto-execution, no hedging.
Shows pair, direction, strength/gap, confluence agreement, and text-described zones.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QFrame, QHeaderView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from typing import Dict, Optional
from datetime import datetime
import config
from layer2_technical import TechnicalAnalyzer
from confluence_filter import ConfluenceFilter
from database import Database


class ConfluenceSignalsTab(QWidget):
    """Confluence signals monitoring — display only, no execution."""
    
    def __init__(self, db: Database, tech_analyzer: TechnicalAnalyzer):
        super().__init__()
        
        self.db = db
        self.tech_analyzer = tech_analyzer
        self.confluence = ConfluenceFilter(tech_analyzer, db=db)
        
        self._init_ui()
        self._setup_auto_refresh()
    
    def _init_ui(self):
        """Build UI layout."""
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # ====== Confluence Status Card ======
        card = self._build_status_card()
        layout.addWidget(card)
        
        # ====== Active Signals Table ======
        heading = QLabel("Confluence Signals (Layer 1 + Layer 2)")
        heading.setProperty("heading", True)
        layout.addWidget(heading)
        
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(8)
        self.signals_table.setHorizontalHeaderLabels([
            "Pair", "Signal", "Entry", "SL", "TP", "L1 Gap", "Z-Score", "Confidence"
        ])
        self.signals_table.setRowCount(10)
        
        layout.addWidget(self.signals_table)
        
        # ====== Controls ======
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh Signals")
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self._refresh_signals)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def _build_status_card(self) -> QFrame:
        """Build confluence status card."""
        card = QFrame()
        card.setObjectName("statusCard")
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        title = QLabel("CONFLUENCE STATUS")
        title.setProperty("subheading", True)
        layout.addWidget(title)
        
        # Layer 1 status
        l1 = QHBoxLayout()
        l1.addWidget(QLabel("Layer 1 (Fundamental):"))
        self.layer1_status_label = QLabel("No bias")
        self.layer1_status_label.setStyleSheet("font-weight: 700;")
        l1.addWidget(self.layer1_status_label)
        l1.addStretch()
        layout.addLayout(l1)

        # Directional Bias Matrix display
        bl = QHBoxLayout()
        bl.addWidget(QLabel("Macro Boundaries:"))
        self.bias_matrix_label = QLabel("No bias matrix")
        self.bias_matrix_label.setStyleSheet("color: #8e44ad; font-size: 12px;")
        bl.addWidget(self.bias_matrix_label)
        bl.addStretch()
        layout.addLayout(bl)
        
        # Layer 2 status
        l2 = QHBoxLayout()
        l2.addWidget(QLabel("Layer 2 (Technical):"))
        self.layer2_status_label = QLabel("No extreme")
        self.layer2_status_label.setStyleSheet("color: #95a5a6;")
        l2.addWidget(self.layer2_status_label)
        l2.addStretch()
        layout.addLayout(l2)
        
        # Confluence result
        cf = QHBoxLayout()
        cf.addWidget(QLabel("Confluence Result:"))
        self.confluence_status_label = QLabel("✕ NO CONFLUENCE")
        self.confluence_status_label.setStyleSheet("color: #e74c3c; font-weight: 700; font-size: 14px;")
        cf.addWidget(self.confluence_status_label)
        cf.addStretch()
        layout.addLayout(cf)

        # Matrix cross (S.A.T.O.R.I.)
        mx = QHBoxLayout()
        mx.addWidget(QLabel("Matrix Cross:"))
        self.matrix_cross_label = QLabel("—")
        self.matrix_cross_label.setStyleSheet("font-weight: 700; color: #8e44ad;")
        mx.addWidget(self.matrix_cross_label)
        mx.addStretch()
        layout.addLayout(mx)

        self.matrix_detail_label = QLabel("")
        self.matrix_detail_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        layout.addWidget(self.matrix_detail_label)

        card.setLayout(layout)
        return card
    
    def set_layer1_signal(self, strongest: str, weakest: str, gap: float,
                           bias_matrix: dict = None):
        """Update Layer 1 directional bias matrix from Dashboard."""
        self.confluence.set_layer1_bias(strongest, weakest, gap, bias_matrix)
        self._refresh_signals()
    
    def _refresh_signals(self):
        """Refresh confluence signal display — single matrix build."""
        try:
            cf = self.confluence

            should_enter, reason, strength, sl_tp = cf.check_entry_confluence()

            m = cf.matrix
            mr = m.get_report() if m else {}
            bias = getattr(cf, 'bias_matrix', {})

            if bias:
                parts = []
                for ccy in config.CURRENCIES:
                    d = bias.get(ccy, {}).get("direction", "—")
                    if d == "STRONG":
                        parts.append(f"{ccy}↑")
                    elif d == "WEAK":
                        parts.append(f"{ccy}↓")
                    else:
                        parts.append(f"{ccy}—")
                self.bias_matrix_label.setText("  ".join(parts))
            else:
                self.bias_matrix_label.setText("No bias matrix")

            mc = mr.get("matrix_cross", "—")
            gap = mr.get("divergence_gap", 0)
            has_div = mr.get("has_divergence", False)
            ranked = mr.get("ranked", [])

            if mc and mc != "N/A":
                self.matrix_cross_label.setText(f"{mc} (spread: {gap:.2f}σ)")
                color = "#e74c3c" if has_div else "#8e44ad"
                self.matrix_cross_label.setStyleSheet(f"font-weight: bold; color: {color};")
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

            if should_enter:
                l1s = cf.layer1_strongest or "—"
                l1w = cf.layer1_weakest or "—"
                self.layer1_status_label.setText(f"PAR {l1s}/{l1w} (Gap: {cf.layer1_gap:.1f})")

                pair = f"{cf.layer1_strongest}_{cf.layer1_weakest}" if cf.layer1_strongest else "—"
                z_score = self.tech_analyzer.get_z_score(pair) if pair != "—" else 0
                self.layer2_status_label.setText(f"TCH {pair} Z-score: {z_score:.2f}")
                self.layer2_status_label.setStyleSheet("color: #27ae60;")

                label_text = f"✅ MATRIX DIVERGENCE: {strength:.0f}%" if has_div else f"✅ CONFLUENCE: {strength:.0f}%"
                self.confluence_status_label.setText(label_text)
                self.confluence_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                self._populate_signal_table(strength)
            else:
                self.layer1_status_label.setText("No signal")
                self.layer2_status_label.setText("No extreme")
                self.layer2_status_label.setStyleSheet("color: #95a5a6;")
                self.confluence_status_label.setText("✕ NO CONFLUENCE")
                self.confluence_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

        except Exception as e:
            print(f"[Confluence] Error refreshing: {e}")
    
    def _populate_signal_table(self, confluence_strength: float):
        report = self.confluence.get_confluence_report()
        signals = self.confluence.get_all_signals()

        self.signals_table.clearContents()
        row = 0

        for pair_key, signal in signals.items():
            if row >= self.signals_table.rowCount():
                break

            def _item(text, align=True):
                item = QTableWidgetItem(str(text))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if align:
                    item.setTextAlignment(Qt.AlignCenter)
                return item

            # 0: Pair
            self.signals_table.setItem(row, 0, _item(pair_key, False))

            # 1: Signal CALL/SHORT
            direction = signal.get('direction', '')
            signal_text = "CALL" if direction == 'LONG' else "SHORT"
            sig_item = _item(signal_text)
            sig_item.setForeground(QColor("#27ae60") if signal_text == "CALL" else QColor("#e74c3c"))
            sig_item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self.signals_table.setItem(row, 1, sig_item)

            # 2: Entry
            entry = signal.get('entry')
            self.signals_table.setItem(row, 2, _item(f"{entry:.5f}" if entry else "—"))

            # 3: SL
            sl = signal.get('sl')
            self.signals_table.setItem(row, 3, _item(f"{sl:.5f}" if sl else "—"))

            # 4: TP
            tp = signal.get('tp')
            self.signals_table.setItem(row, 4, _item(f"{tp:.5f}" if tp else "—"))

            # 5: L1 Gap
            self.signals_table.setItem(row, 5, _item(f"{report.get('layer1_gap', 0):.1f}"))

            # 6: Z-Score
            z = report.get('layer2_z_score', 0)
            if signal.get('type') == 'MATRIX_DIVERGENCE':
                z = report.get('matrix_cross_z', 0)
            self.signals_table.setItem(row, 6, _item(f"{z:.2f}"))

            # 7: Confidence
            strength = signal.get('strength', confluence_strength)
            conf_item = _item(f"{strength:.0f}%")
            conf_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.signals_table.setItem(row, 7, conf_item)

            row += 1
    
    def _setup_auto_refresh(self):
        """Setup automatic refresh timer."""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_signals)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
