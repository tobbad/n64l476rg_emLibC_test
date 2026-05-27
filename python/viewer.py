#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RadioBell Log Viewer
Displays the device event timeline from log files or live serial ports.

Usage:
  python viewer.py                       # GUI only
  python viewer.py log/slot_1.txt ...    # pre-load files
  python viewer.py /dev/ttyUSB0         # auto-connect serial port
"""
import sys
import re
from pathlib import Path
from datetime import datetime

# ── PyQt5 / PyQt6 compatibility ───────────────────────────────────────────────
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
        QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QGroupBox,
        QPushButton, QLabel, QFileDialog, QDialog, QComboBox,
        QDialogButtonBox, QSplitter, QAction, QHeaderView,
        QAbstractItemView, QMessageBox, QToolBar, QFrame,
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex, QMutexLocker
    from PyQt5.QtGui import QColor, QBrush, QFont
    # Qt5: enums are plain ints
    _NO_EDIT   = QAbstractItemView.NoEditTriggers
    _SEL_ROWS  = QAbstractItemView.SelectRows
    _H_SPLIT   = Qt.Horizontal
    _ALIGN_RV  = int(Qt.AlignRight | Qt.AlignVCenter)
    _BTN_OC    = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
    _EXEC      = lambda obj: obj.exec_()
except ImportError:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
        QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QGroupBox,
        QPushButton, QLabel, QFileDialog, QDialog, QComboBox,
        QDialogButtonBox, QSplitter, QAction, QHeaderView,
        QAbstractItemView, QMessageBox, QToolBar, QFrame,
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex, QMutexLocker
    from PyQt6.QtGui import QColor, QBrush, QFont
    _NO_EDIT   = QAbstractItemView.EditTrigger.NoEditTriggers
    _SEL_ROWS  = QAbstractItemView.SelectionBehavior.SelectRows
    _H_SPLIT   = Qt.Orientation.Horizontal
    _ALIGN_RV  = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    _BTN_OC    = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    _EXEC      = lambda obj: obj.exec()

# ── Import parsing logic from parse_logs.py ───────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from parse_logs import (
    parse_events, assign_t_ms, deduplicate,
    parse_anchors, tick_to_epoch_ms, extract_tick_msg,
)

# ── Constants ─────────────────────────────────────────────────────────────────
BAUD_DEFAULT = 115200

COLS     = ['t_ms', 'dev', 'type', 'af', 'hub', 'D', 'info', 'source']
COL_W    = [110,     40,    65,     35,   40,    22,   0,      120]   # 0 = stretch
CI       = {c: i for i, c in enumerate(COLS)}

TYPE_META = {
    #  type     label              bg-color
    'TX':     ('TX  (data sent)',     '#BDE0FF'),
    'RX':     ('RX  (data recv)',     '#B5F0C0'),
    'ACK_TX': ('ACK sent  >>',        '#FFD9A0'),
    'ACK_RX': ('ACK received  <<',    '#FFF4A0'),
}

SLOT_PALETTE = [  # per-device tint for the dev column
    '#E8F4FF', '#E8FFE8', '#FFF0E8', '#F5E8FF',
    '#E8FFFF', '#FFE8F5', '#F0FFE8', '#FFE8E8',
]


def _color(event_type: str) -> QColor:
    return QColor(TYPE_META.get(event_type, ('', '#FFFFFF'))[1])


def _row_data(e: dict) -> list[str]:
    """Convert event dict → list of display strings (one per column)."""
    t   = f"{e.get('t_ms', 0):010d}"
    dev = str(e['device_slot'])
    typ = e['type']
    af  = str(e['af_slot'])  if e.get('af_slot')  is not None else ''
    hub = str(e['hubCnt'])   if e.get('hubCnt')   is not None else ''
    d   = '●' if e.get('dirty') else ''

    if typ in ('TX', 'RX'):
        active = '  '.join(
            f"{k}={v}" for k, v in e.get('state', {}).items() if v != 'OFF'
        ) or '—'
        info = active
    elif typ == 'ACK_TX':
        info = '>> ACK sent'
    else:
        info = f"<< from slot {e.get('from_slot', '?')}"

    src = e.get('source_file', '')
    return [t, dev, typ, af, hub, d, info, src]


# ── Live serial parser (streaming, line-by-line) ──────────────────────────────
class _StreamParser:
    """
    Accumulates lines from a serial port and emits complete events.
    Mirrors parse_events() but operates on a stream instead of a full file.
    """
    def __init__(self, source_name: str):
        self.source_name  = source_name
        self.device_slot  = None
        self.anchors: list = []
        self._frame       = None
        self._labels      = None

    def _epoch(self, tick: int) -> int | None:
        return tick_to_epoch_ms(tick, self.anchors) if self.anchors else None

    def _base(self, tick: int, typ: str) -> dict:
        return {
            'source_file': self.source_name,
            'device_slot': self.device_slot or 0,
            'type': typ,
            'tick': tick,
            '_epoch_ms': self._epoch(tick),
        }

    def _flush(self) -> dict | None:
        f, self._frame, self._labels = self._frame, None, None
        return f

    def feed(self, line: str) -> list[dict]:
        """Feed one raw line; returns list of complete events (0, 1, or 2)."""
        tick, msg = extract_tick_msg(line)
        if msg is None:
            return []

        emitted = []

        # Device slot from EEPROM header
        if self.device_slot is None:
            m = re.match(r'my_slot\s*=\s*(\d+)', msg)
            if m:
                self.device_slot = int(m.group(1))

        # TXFRAME / RXFRAME start
        m = re.match(r'(TXFRAME|RXFRAME)\s*\(c:', msg)
        if m:
            if self._frame:
                emitted.append(self._flush())
            f = self._base(tick, 'TX' if 'TX' in m.group(1) else 'RX')
            f.update({'af_slot': None, 'pl_slot': None, 'hubCnt': None,
                      'state': {}, 'dirty': False})
            self._frame = f
            return emitted

        # Continue building pending frame
        if self._frame:
            pf = self._frame
            if (m := re.match(r'AF\s+slot\s*=\s*(\d+)', msg)):
                pf['af_slot'] = int(m.group(1)); return emitted
            if (m := re.match(r'PL\s+slot\s*=\s*(\d+)', msg)):
                pf['pl_slot'] = int(m.group(1)); return emitted
            if (m := re.match(r'hubCnt\s*=\s*(\d+)', msg)):
                pf['hubCnt'] = int(m.group(1)); return emitted
            if msg == 'state':
                return emitted
            if (m := re.match(r'label\s*=\s*(.*)', msg)):
                self._labels = m.group(1).split(); return emitted
            if (m := re.match(r'State\s*=\s*(.*)', msg)) and self._labels:
                vals = m.group(1).split()
                pf['state'] = {
                    self._labels[k].lower(): vals[k]
                    for k in range(min(len(self._labels), len(vals)))
                }
                return emitted
            if msg == 'Dirty':
                pf['dirty'] = True
                emitted.append(self._flush())
                return emitted
            # Unrelated line → flush the pending frame first
            emitted.append(self._flush())

        # ACK sent (bare line, not ">>> ...")
        if re.match(r'SM_STATE_SEND_ACK\s*$', msg):
            emitted.append({**self._base(tick, 'ACK_TX')})
            return emitted

        # ACK received
        if (m := re.match(r'SM_STATE_ACK_RECEIVED\s+from\s+slot\s+(\d+)', msg)):
            e = self._base(tick, 'ACK_RX')
            e['from_slot'] = int(m.group(1))
            emitted.append(e)
            return emitted

        return emitted


# ── Serial worker thread ──────────────────────────────────────────────────────
class SerialWorker(QThread):
    event_ready   = pyqtSignal(dict)
    status_update = pyqtSignal(str)

    def __init__(self, port: str, baud: int = BAUD_DEFAULT):
        super().__init__()
        self._port    = port
        self._baud    = baud
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        try:
            import serial
        except ImportError:
            self.status_update.emit("pyserial not installed — run: pip install pyserial")
            return

        try:
            ser = serial.Serial(self._port, self._baud, timeout=1.0)
        except Exception as ex:
            self.status_update.emit(f"Cannot open {self._port}: {ex}")
            return

        parser = _StreamParser(self._port)
        connect_epoch = int(datetime.now().timestamp() * 1000)

        try:
            ser.write(b'R')   # request device reset/info dump
        except Exception:
            pass

        first_tick_seen = False

        while self._running:
            try:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode('ascii', errors='replace').rstrip('\r\n')

                # Build initial anchor from the very first tick seen
                if not first_tick_seen:
                    tick, _ = extract_tick_msg(line)
                    if tick is not None:
                        parser.anchors.append((connect_epoch, tick))
                        first_tick_seen = True

                for evt in parser.feed(line):
                    self.event_ready.emit(evt)

            except Exception as ex:
                if self._running:
                    self.status_update.emit(f"Serial error: {ex}")
                break

        try:
            ser.close()
        except Exception:
            pass

        self.status_update.emit(f"Disconnected from {self._port}")


# ── Serial port dialog ────────────────────────────────────────────────────────
class SerialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect Serial Port")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)

        grp = QGroupBox("Port")
        gl   = QVBoxLayout(grp)
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        gl.addWidget(self.port_combo)
        ref = QPushButton("Refresh list")
        ref.clicked.connect(self._refresh)
        gl.addWidget(ref)
        layout.addWidget(grp)

        grp2 = QGroupBox("Baud rate")
        gl2  = QHBoxLayout(grp2)
        self.baud_combo = QComboBox()
        for b in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600):
            self.baud_combo.addItem(str(b))
        self.baud_combo.setCurrentText(str(BAUD_DEFAULT))
        gl2.addWidget(self.baud_combo)
        layout.addWidget(grp2)

        bb = QDialogButtonBox(_BTN_OC)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

        self._refresh()

    def _refresh(self):
        self.port_combo.clear()
        try:
            import serial.tools.list_ports
            for p in sorted(serial.tools.list_ports.comports(), key=lambda x: x.device):
                self.port_combo.addItem(f"{p.device}  —  {p.description}", p.device)
        except Exception:
            pass
        if self.port_combo.count() == 0:
            self.port_combo.addItem("(no ports found)")

    @property
    def port(self) -> str:
        d = self.port_combo.currentData()
        return d if d else self.port_combo.currentText().split()[0]

    @property
    def baud(self) -> int:
        return int(self.baud_combo.currentText())


# ── Main window ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RadioBell Log Viewer")
        self.resize(1200, 700)

        self._events: list[dict]           = []
        self._workers: list[SerialWorker]  = []
        self._pending: list[dict]          = []
        self._mutex   = QMutex()
        self._auto_scroll = True

        self._build_ui()
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_pending)
        self._flush_timer.start(250)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── toolbar ──────────────────────────────────────────────────────────
        tb: QToolBar = self.addToolBar("Main")
        tb.setMovable(False)

        a = tb.addAction("📂  Open file(s)")
        a.setToolTip("Load one or more .txt log files")
        a.triggered.connect(self._open_files)

        a = tb.addAction("🔌  Add serial port")
        a.setToolTip("Connect to a live device via serial/COM port")
        a.triggered.connect(self._add_serial)

        tb.addSeparator()

        self._as_action = tb.addAction("⬇  Auto-scroll")
        self._as_action.setCheckable(True)
        self._as_action.setChecked(True)
        self._as_action.toggled.connect(lambda v: setattr(self, '_auto_scroll', v))

        tb.addSeparator()

        a = tb.addAction("🗑  Clear")
        a.triggered.connect(self._clear)

        # ── splitter: filter panel | table ───────────────────────────────────
        splitter = QSplitter(_H_SPLIT)

        # Filter panel
        panel = QWidget()
        panel.setFixedWidth(185)
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(4, 6, 4, 4)

        # Device checkboxes (populated dynamically)
        self._dev_grp    = QGroupBox("Devices")
        self._dev_layout = QVBoxLayout(self._dev_grp)
        self._dev_layout.setSpacing(3)
        self._dev_checks: dict[int, QCheckBox] = {}
        pv.addWidget(self._dev_grp)

        # Event type checkboxes
        type_grp = QGroupBox("Event type")
        tv       = QVBoxLayout(type_grp)
        tv.setSpacing(3)
        self._type_checks: dict[str, QCheckBox] = {}
        for typ, (label, color) in TYPE_META.items():
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setStyleSheet(
                f"QCheckBox {{ background:{color}; padding:2px 4px; "
                f"border-radius:3px; }}"
            )
            cb.stateChanged.connect(self._apply_filter)
            self._type_checks[typ] = cb
            tv.addWidget(cb)
        pv.addWidget(type_grp)
        pv.addStretch()

        # Sources list
        src_grp = QGroupBox("Sources")
        sv      = QVBoxLayout(src_grp)
        self._src_label = QLabel("—")
        self._src_label.setWordWrap(True)
        self._src_label.setStyleSheet("font-size:8pt;")
        sv.addWidget(self._src_label)
        pv.addWidget(src_grp)

        splitter.addWidget(panel)

        # Event table
        self._table = QTableWidget(0, len(COLS))
        self._table.setHorizontalHeaderLabels(COLS)
        self._table.setEditTriggers(_NO_EDIT)
        self._table.setSelectionBehavior(_SEL_ROWS)
        self._table.setAlternatingRowColors(False)
        self._table.setSortingEnabled(False)
        self._table.verticalHeader().setDefaultSectionSize(21)
        self._table.verticalHeader().setVisible(False)
        self._table.setFont(
            QFont("Consolas", 9) if sys.platform == "win32" else QFont("Monospace", 9)
        )
        hdr = self._table.horizontalHeader()
        for col, w in enumerate(COL_W):
            if w == 0:
                hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch
                                         if hasattr(QHeaderView, 'ResizeMode')
                                         else QHeaderView.Stretch)
            else:
                self._table.setColumnWidth(col, w)

        splitter.addWidget(self._table)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # Status bar
        self._status = QLabel("No data loaded.")
        self.statusBar().addWidget(self._status)

    # ── File loading ──────────────────────────────────────────────────────────
    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open log file(s)",
            str(Path(__file__).parent / "log"),
            "Log files (*.txt);;All files (*)"
        )
        self._load_paths([Path(p) for p in paths])

    def _load_paths(self, paths: list[Path]):
        new_events = []
        for p in paths:
            if not p.is_file():
                continue
            lines = p.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
            new_events.extend(parse_events(p.name, lines))

        if not new_events:
            return
        combined = deduplicate(self._events + new_events)
        assign_t_ms(combined)
        combined.sort(key=lambda e: e.get('t_ms', 0))
        self._events = combined
        self._rebuild_table()

    # ── Serial port ───────────────────────────────────────────────────────────
    def _add_serial(self):
        dlg = SerialDialog(self)
        if not _EXEC(dlg):
            return
        self._connect_port(dlg.port, dlg.baud)

    def _connect_port(self, port: str, baud: int = BAUD_DEFAULT):
        worker = SerialWorker(port, baud)
        worker.event_ready.connect(self._on_serial_event)
        worker.status_update.connect(lambda m: self.statusBar().showMessage(m, 4000))
        self._workers.append(worker)
        worker.start()
        self.statusBar().showMessage(f"Connected to {port} @ {baud}", 3000)

    def _on_serial_event(self, event: dict):
        with QMutexLocker(self._mutex):
            self._pending.append(event)

    def _flush_pending(self):
        with QMutexLocker(self._mutex):
            if not self._pending:
                return
            batch, self._pending = self._pending[:], []

        combined = deduplicate(self._events + batch)
        assign_t_ms(combined)
        combined.sort(key=lambda e: e.get('t_ms', 0))

        if len(combined) == len(self._events):
            return   # all duplicates, nothing new
        self._events = combined
        self._rebuild_table()

    # ── Table ─────────────────────────────────────────────────────────────────
    def _rebuild_table(self):
        self._table.setRowCount(0)

        # Sync device checkboxes
        slots = sorted({e['device_slot'] for e in self._events
                        if e['device_slot'] is not None})
        for slot in slots:
            if slot not in self._dev_checks:
                cb = QCheckBox(f"Slot {slot}")
                cb.setChecked(True)
                cb.setStyleSheet(
                    f"QCheckBox {{ background:{SLOT_PALETTE[slot % len(SLOT_PALETTE)]};"
                    f" padding:2px 4px; border-radius:3px; }}"
                )
                cb.stateChanged.connect(self._apply_filter)
                self._dev_checks[slot] = cb
                self._dev_layout.addWidget(cb)

        active_types = {t for t, cb in self._type_checks.items() if cb.isChecked()}
        active_devs  = {s for s, cb in self._dev_checks.items()  if cb.isChecked()}

        for e in self._events:
            visible = (e['type'] in active_types and
                       e.get('device_slot') in active_devs)
            self._append_row(e, hidden=not visible)

        self._update_status()

        if self._auto_scroll:
            self._table.scrollToBottom()

        # Source list
        srcs = sorted({e['source_file'] for e in self._events})
        self._src_label.setText('\n'.join(srcs) or '—')

    def _append_row(self, e: dict, hidden: bool = False):
        row = self._table.rowCount()
        self._table.insertRow(row)
        bg    = QBrush(_color(e['type']))
        align = {CI['t_ms']: _ALIGN_RV, CI['dev']: _ALIGN_RV,
                 CI['af']: _ALIGN_RV, CI['hub']: _ALIGN_RV, CI['D']: _ALIGN_RV}
        for col, text in enumerate(_row_data(e)):
            item = QTableWidgetItem(text)
            item.setBackground(bg)
            if col in align:
                item.setTextAlignment(align[col])
            self._table.setItem(row, col, item)
        if hidden:
            self._table.setRowHidden(row, True)

    def _apply_filter(self):
        active_types = {t for t, cb in self._type_checks.items() if cb.isChecked()}
        active_devs  = {s for s, cb in self._dev_checks.items()  if cb.isChecked()}
        for row in range(self._table.rowCount()):
            typ = (self._table.item(row, CI['type']) or QTableWidgetItem()).text()
            dev = (self._table.item(row, CI['dev'])  or QTableWidgetItem()).text()
            visible = (typ in active_types and
                       dev.isdigit() and int(dev) in active_devs)
            self._table.setRowHidden(row, not visible)
        self._update_status()

    def _update_status(self):
        total = len(self._events)
        shown = sum(1 for r in range(self._table.rowCount())
                    if not self._table.isRowHidden(r))
        slots = sorted({e['device_slot'] for e in self._events
                        if e['device_slot'] is not None})
        by_type = {t: sum(1 for e in self._events if e['type'] == t)
                   for t in ('TX', 'RX', 'ACK_TX', 'ACK_RX')}
        self._status.setText(
            f"{total} events ({by_type['TX']} TX  {by_type['RX']} RX  "
            f"{by_type['ACK_TX']} ACK>  {by_type['ACK_RX']} ACK<)  "
            f"| {shown} shown  "
            f"| slots: {', '.join(str(s) for s in slots)}"
        )

    def _clear(self):
        self._events.clear()
        self._table.setRowCount(0)
        for cb in list(self._dev_checks.values()):
            self._dev_layout.removeWidget(cb)
            cb.deleteLater()
        self._dev_checks.clear()
        self._src_label.setText('—')
        self._status.setText("No data loaded.")

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        for w in self._workers:
            w.stop()
            w.wait(1500)
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RadioBell Log Viewer")
    app.setStyle("Fusion")

    win = MainWindow()
    win.show()

    # CLI arguments: .txt files → pre-load; anything else → try as serial port
    if len(sys.argv) > 1:
        files  = [Path(a) for a in sys.argv[1:] if Path(a).suffix == '.txt']
        ports  = [a for a in sys.argv[1:] if Path(a).suffix != '.txt']
        if files:
            win._load_paths(files)
        for port in ports:
            win._connect_port(port)

    try:
        sys.exit(app.exec())
    except AttributeError:
        sys.exit(app.exec_())


if __name__ == '__main__':
    main()
