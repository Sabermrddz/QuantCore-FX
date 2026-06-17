from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QCheckBox, QMessageBox, QStatusBar, QProgressBar,
    QHeaderView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QFont, QBrush
from typing import Dict, Optional
from datetime import datetime, timezone
import config
from layer2_technical import TechnicalAnalyzer
from data_feeder import Mt5DataFeeder, MockDataFeeder
from currency_strength_matrix import CurrencyStrengthMatrix


class DataStreamerThread(QThread):
    """Background thread for data source polling."""

    price_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    connected = pyqtSignal(bool)

    def __init__(self, data_feeder, instruments):
        super().__init__()
        self.feeder = data_feeder
        self.instruments = instruments
        self.running = True

    def run(self):
        try:
            if not self.feeder.test_connection():
                self.connected.emit(False)
                self.error_occurred.emit("Failed to connect to data source")
                return

            self.connected.emit(True)
            self.feeder.stream_prices(self.instruments, callback=self._on_price)

        except Exception as e:
            self.error_occurred.emit(str(e))
            self.connected.emit(False)

    def _on_price(self, price_data):
        self.price_updated.emit(price_data)

    def stop(self):
        self.running = False
        if hasattr(self.feeder, 'stop_streaming'):
            self.feeder.stop_streaming()


class Layer2MonitorTab(QWidget):
    """Layer 2 technical analysis monitoring tab.

    Task 4.1 — Dynamic Session Visualizations:
    - Active market session indicator (Tokyo / London / New York)
    - High-contrast conditional formatting for ±2σ currency strength cells
    """

    def __init__(self, technical_analyzer: TechnicalAnalyzer = None):
        super().__init__()

        self.tech_analyzer = technical_analyzer or TechnicalAnalyzer()
        self.data_feeder = None
        self.streamer_thread = None
        self.connected = False

        # Persistent matrix to retain SessionTracker state across refreshes
        self.matrix = CurrencyStrengthMatrix()

        self._init_ui()
        self._setup_data_source()
        self._refresh_display()

    def _init_ui(self):
        """Build UI layout."""
        layout = QVBoxLayout()

        # ====== Connection Panel ======
        connection_layout = QHBoxLayout()

        connection_layout.addWidget(QLabel("Data Source:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Mock (Test)", "MT5 (Live)"])
        self.source_combo.setCurrentIndex(0)
        connection_layout.addWidget(self.source_combo)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        connection_layout.addWidget(self.connect_btn)

        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        connection_layout.addWidget(self.status_label)

        connection_layout.addStretch()
        layout.addLayout(connection_layout)
        layout.addSpacing(10)

        # ====== Active Session Indicator (Task 4.1) ======
        session_layout = QHBoxLayout()
        session_layout.addWidget(QLabel("Active Session:"))
        self.session_label = QLabel("—")
        self.session_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; padding: 2px 8px; "
            "background-color: #ecf0f1; border-radius: 4px;"
        )
        session_layout.addWidget(self.session_label)
        session_layout.addStretch()
        layout.addLayout(session_layout)
        layout.addSpacing(5)

        # ====== Z-Score Table ======
        layout.addWidget(QLabel("Technical Analysis — All Pairs"))

        self.tech_table = QTableWidget()
        self.tech_table.setColumnCount(7)
        self.tech_table.setHorizontalHeaderLabels([
            "Pair", "Current Price", "Z-Score", "Volatility", "Mean Price", "Status", "Signal"
        ])
        self.tech_table.setRowCount(28)
        self.tech_table.setAlternatingRowColors(True)
        self.tech_table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.tech_table)
        layout.addSpacing(10)

        # ====== Alerts Panel ======
        alerts_layout = QHBoxLayout()

        alerts_layout.addWidget(QLabel("Overbought Pairs:"))
        self.overbought_label = QLabel("—")
        self.overbought_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        alerts_layout.addWidget(self.overbought_label)

        alerts_layout.addSpacing(20)

        alerts_layout.addWidget(QLabel("Oversold Pairs:"))
        self.oversold_label = QLabel("—")
        self.oversold_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        alerts_layout.addWidget(self.oversold_label)

        alerts_layout.addStretch()
        layout.addLayout(alerts_layout)
        layout.addSpacing(10)

        # ====== Currency Strength Matrix ======
        matrix_group = QWidget()
        matrix_layout = QVBoxLayout(matrix_group)
        matrix_layout.setContentsMargins(0, 0, 0, 0)

        matrix_layout.addWidget(QLabel("Currency Strength Matrix (S.A.T.O.R.I.)"))
        self.matrix_cross_label = QLabel("Matrix Cross: —")
        self.matrix_cross_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")
        matrix_layout.addWidget(self.matrix_cross_label)

        self.divergence_label = QLabel("Divergence Gap: 0.0")
        self.divergence_label.setStyleSheet("color: #7f8c8d;")
        matrix_layout.addWidget(self.divergence_label)

        self.strong_alert = QLabel("")
        matrix_layout.addWidget(self.strong_alert)
        self.weak_alert = QLabel("")
        matrix_layout.addWidget(self.weak_alert)

        self.matrix_table = QTableWidget()
        self.matrix_table.setColumnCount(5)
        self.matrix_table.setHorizontalHeaderLabels([
            "Rank", "Currency", "Strength Z", "Direction", "Session SRV"
        ])
        self.matrix_table.setRowCount(8)
        self.matrix_table.setMaximumHeight(240)
        self.matrix_table.horizontalHeader().setStretchLastSection(True)
        matrix_layout.addWidget(self.matrix_table)

        layout.addWidget(matrix_group)
        layout.addSpacing(10)

        # ====== Refresh Button ======
        button_layout = QHBoxLayout()

        self.auto_refresh_check = QCheckBox("Auto-refresh (every 1s)")
        self.auto_refresh_check.setChecked(True)
        button_layout.addWidget(self.auto_refresh_check)

        refresh_btn = QPushButton("Refresh Now")
        refresh_btn.clicked.connect(self._refresh_display)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)
        layout.addStretch()

        self.setLayout(layout)

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_display)

    def _setup_data_source(self):
        """Initialize data source."""
        source = self.source_combo.currentText()
        if "MT5" in source:
            self.data_feeder = Mt5DataFeeder()
        else:
            self.data_feeder = MockDataFeeder()

    def _on_connect_clicked(self):
        """Handle connect button click."""
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _seed_historical_bars(self):
        """Seed the analyzer with 24h of historical M5 bar data for stable Z-scores."""
        if hasattr(self.data_feeder, 'generate_mock_bars'):
            bars = self.data_feeder.generate_mock_bars(n_bars=config.BAR_LOOKBACK_BARS)
        elif hasattr(self.data_feeder, 'fetch_historical_closes_all_pairs'):
            bars = self.data_feeder.fetch_historical_closes_all_pairs(
                days=1, interval="5min"
            )
        else:
            return
        self.tech_analyzer.seed_bars(bars)

    def _connect(self):
        """Connect to data source."""
        try:
            if not self.data_feeder.test_connection():
                reason = getattr(self.data_feeder, 'last_error', 'Unknown error')
                QMessageBox.warning(self, "Connection Error", f"Failed to connect to data source:\n{reason}")
                return

            # Seed bar_history with 24h of M5 close prices so Z-scores are
            # anchored to a meaningful multi-hour frame, not tick noise.
            self._seed_historical_bars()

            instruments = self.data_feeder.get_all_major_pairs()
            self.streamer_thread = DataStreamerThread(self.data_feeder, instruments)
            self.streamer_thread.price_updated.connect(self._on_price_received)
            self.streamer_thread.error_occurred.connect(self._on_streamer_error)
            self.streamer_thread.connected.connect(self._on_connected)
            self.streamer_thread.start()

            if self.auto_refresh_check.isChecked():
                self.refresh_timer.start(1000)

            self.connected = True
            self.connect_btn.setText("Disconnect")
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self._refresh_display()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed: {e}")

    def _disconnect(self):
        """Disconnect from data source."""
        if self.streamer_thread:
            self.streamer_thread.stop()
            self.streamer_thread.quit()
            self.streamer_thread.wait()

        self.refresh_timer.stop()

        self.connected = False
        self.connect_btn.setText("Connect")
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

    def _on_price_received(self, price_data):
        """Handle price update from data feeder."""
        pair = price_data.get('pair')
        mid_price = price_data.get('mid')

        if pair and mid_price:
            self.tech_analyzer.add_price_data(pair, mid_price)
            self._refresh_display()

    def _on_connected(self, is_connected):
        """Handle connection status change."""
        if is_connected:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

    def _on_streamer_error(self, error_msg):
        """Handle streamer error."""
        print(f"[Layer2] Streamer error: {error_msg}")

    def _refresh_display(self):
        """Refresh the technical analysis display."""
        try:
            z_scores = self.tech_analyzer.get_all_z_scores()
            overbought = self.tech_analyzer.get_overbought_pairs()
            oversold = self.tech_analyzer.get_oversold_pairs()

            for row, (pair, z_score) in enumerate(sorted(z_scores.items())):
                if row >= self.tech_table.rowCount():
                    break

                status = self.tech_analyzer.get_status_for_pair(pair)

                pair_item = QTableWidgetItem(pair)
                pair_item.setFlags(pair_item.flags() & ~Qt.ItemIsEditable)
                self.tech_table.setItem(row, 0, pair_item)

                last_price = self.tech_analyzer.get_last_price(pair)
                price_text = f"{last_price:.4f}" if last_price else "—"
                price_item = QTableWidgetItem(price_text)
                price_item.setFlags(price_item.flags() & ~Qt.ItemIsEditable)
                self.tech_table.setItem(row, 1, price_item)

                z_item = QTableWidgetItem(f"{z_score:.2f}")
                z_item.setFlags(z_item.flags() & ~Qt.ItemIsEditable)
                z_item.setTextAlignment(Qt.AlignCenter)

                if abs(z_score) >= config.Z_SCORE_THRESHOLD:
                    z_item.setBackground(QColor("#ffebee"))
                    z_item.setForeground(QColor("#c62828"))

                self.tech_table.setItem(row, 2, z_item)

                vol_item = QTableWidgetItem(f"{status['volatility']:.4f}")
                vol_item.setFlags(vol_item.flags() & ~Qt.ItemIsEditable)
                self.tech_table.setItem(row, 3, vol_item)

                mean_item = QTableWidgetItem(f"{status['mean_price']:.4f}")
                mean_item.setFlags(mean_item.flags() & ~Qt.ItemIsEditable)
                self.tech_table.setItem(row, 4, mean_item)

                status_item = QTableWidgetItem(status['status'])
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)

                if "OVERBOUGHT" in status['status']:
                    status_item.setBackground(QColor("#ffebee"))
                elif "OVERSOLD" in status['status']:
                    status_item.setBackground(QColor("#e8f5e9"))

                self.tech_table.setItem(row, 5, status_item)

                if status['is_extreme']:
                    signal = "EXTREME"
                    signal_item = QTableWidgetItem(signal)
                    signal_item.setBackground(QColor("#fff3e0"))
                else:
                    signal = "Normal"
                    signal_item = QTableWidgetItem(signal)

                signal_item.setFlags(signal_item.flags() & ~Qt.ItemIsEditable)
                self.tech_table.setItem(row, 6, signal_item)

            overbought_text = ", ".join(overbought) if overbought else "None"
            oversold_text = ", ".join(oversold) if oversold else "None"

            self.overbought_label.setText(overbought_text)
            self.oversold_label.setText(oversold_text)

            self.tech_table.resizeColumnsToContents()

            # ====== Currency Strength Matrix (persistent instance) ======
            current_prices = {}
            for pair in z_scores:
                lp = self.tech_analyzer.get_last_price(pair)
                if lp is not None:
                    current_prices[pair] = lp
            self.matrix.update(z_scores, current_prices=current_prices)
            report = self.matrix.get_report()

            matrix_cross = report["matrix_cross"]
            gap = report["divergence_gap"]
            self.matrix_cross_label.setText(
                f"Matrix Cross: {matrix_cross or '—'}  |  Spread: {gap:.2f}σ"
            )

            if report["has_divergence"]:
                self.matrix_cross_label.setStyleSheet(
                    "font-weight: bold; font-size: 13px; color: #e74c3c;"
                )
                self.divergence_label.setText(
                    "DIVERGENCE DETECTED — extreme strength vs extreme weakness"
                )
                self.divergence_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            else:
                self.matrix_cross_label.setStyleSheet(
                    "font-weight: bold; font-size: 13px; color: #2c3e50;"
                )
                self.divergence_label.setText("No extreme divergence")
                self.divergence_label.setStyleSheet("color: #7f8c8d;")

            ob_currencies = report["overbought"]
            os_currencies = report["oversold"]
            self.strong_alert.setText(
                f"Overbought Currencies: {', '.join(ob_currencies) if ob_currencies else 'None'}"
            )
            self.weak_alert.setText(
                f"Oversold Currencies: {', '.join(os_currencies) if os_currencies else 'None'}"
            )

            # ====== Active Session Indicator (Task 4.1) ======
            active_session = report.get("active_session", "—")
            session_colors = {
                "Tokyo": "#8e44ad",
                "London": "#2980b9",
                "New York": "#e67e22",
                "Off-Hours": "#7f8c8d",
            }
            session_color = session_colors.get(active_session, "#7f8c8d")
            self.session_label.setText(active_session)
            self.session_label.setStyleSheet(
                f"font-weight: bold; font-size: 14px; padding: 2px 8px; "
                f"color: white; background-color: {session_color}; "
                f"border-radius: 4px;"
            )

            # ====== Ranked Currency Table with High-Contrast σ (Task 4.1) ======
            ranked = report["ranked"]
            for row, entry in enumerate(ranked):
                ccy = entry[0]
                z_val = entry[1]
                direction = entry[2]
                srv = entry[3] if len(entry) > 3 else 0.0

                rank_item = QTableWidgetItem(str(row + 1))
                rank_item.setFlags(rank_item.flags() & ~Qt.ItemIsEditable)
                rank_item.setTextAlignment(Qt.AlignCenter)
                self.matrix_table.setItem(row, 0, rank_item)

                ccy_item = QTableWidgetItem(ccy)
                ccy_item.setFlags(ccy_item.flags() & ~Qt.ItemIsEditable)
                self.matrix_table.setItem(row, 1, ccy_item)

                z_item = QTableWidgetItem(f"{z_val:.2f}")
                z_item.setFlags(z_item.flags() & ~Qt.ItemIsEditable)
                z_item.setTextAlignment(Qt.AlignCenter)

                # High-contrast σ formatting (Task 4.1)
                threshold = config.Z_SCORE_THRESHOLD
                if z_val >= threshold:
                    z_item.setBackground(QColor("#c62828"))
                    z_item.setForeground(QColor("white"))
                elif z_val <= -threshold:
                    z_item.setBackground(QColor("#2e7d32"))
                    z_item.setForeground(QColor("white"))

                self.matrix_table.setItem(row, 2, z_item)

                dir_item = QTableWidgetItem(direction)
                dir_item.setFlags(dir_item.flags() & ~Qt.ItemIsEditable)
                if direction == "OVERBOUGHT":
                    dir_item.setBackground(QColor("#ffebee"))
                    dir_item.setForeground(QColor("#c62828"))
                elif direction == "OVERSOLD":
                    dir_item.setBackground(QColor("#e8f5e9"))
                    dir_item.setForeground(QColor("#2e7d32"))
                self.matrix_table.setItem(row, 3, dir_item)

                # Session Relative Velocity column
                srv_sign = "+" if srv >= 0 else ""
                srv_item = QTableWidgetItem(f"{srv_sign}{srv:.4f}%")
                srv_item.setFlags(srv_item.flags() & ~Qt.ItemIsEditable)
                srv_item.setTextAlignment(Qt.AlignCenter)
                if abs(srv) > 0.5:
                    srv_item.setBackground(QColor("#fff3e0"))
                self.matrix_table.setItem(row, 4, srv_item)

            self.matrix_table.resizeColumnsToContents()

        except Exception as e:
            print(f"[Layer2] Display error: {e}")

    def closeEvent(self, event):
        """Clean up on close."""
        self._disconnect()
        event.accept()
