#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RadioBell Log Viewer
====================
Displays the event timeline of RadioBell devices from saved log files
or from live serial connections.

File structure
--------------
  Section 1 – CONFIGURATION   : colours, column definitions, help HTML.
               Edit this section to add event types, columns, or change colours.
  Section 2 – PARSING BRIDGE  : imports from parse_logs.py.
  Section 3 – SERIAL I/O      : SerialWorker (QThread) + _StreamParser.
  Section 4 – DIALOGS         : SerialDialog, HelpDialog.
  Section 5 – MAIN WINDOW     : MainWindow class.
  Section 6 – ENTRY POINT     : main(), CLI argument handling.

Usage
-----
  python viewer.py                                 # open GUI, use File menu
  python viewer.py log/slot_1.txt log/slot_3.txt   # pre-load log files
  python viewer.py /dev/ttyUSB0                    # auto-connect serial port
  python viewer.py COM3                            # Windows serial port
"""

import sys
import re
from pathlib import Path
from datetime import datetime

# ── PyQt5 / PyQt6 compatibility ───────────────────────────────────────────────
# viewer.py supports both PyQt5 and PyQt6.
# The try/except block picks whichever is installed.
# All Qt-version-specific enum differences are resolved into plain constants
# (_NO_EDIT, _SEL_ROWS, …) so the rest of the code never needs to branch.
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
        QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QGroupBox,
        QPushButton, QLabel, QFileDialog, QDialog, QComboBox,
        QDialogButtonBox, QSplitter, QHeaderView, QAbstractItemView,
        QMessageBox, QAction, QTextBrowser, QSizePolicy,
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex, QMutexLocker
    from PyQt5.QtGui import QColor, QBrush, QFont, QKeySequence, QIcon

    _NO_EDIT      = QAbstractItemView.NoEditTriggers
    _SEL_ROWS     = QAbstractItemView.SelectRows
    _H_SPLIT      = Qt.Horizontal
    _ALIGN_R      = int(Qt.AlignRight | Qt.AlignVCenter)
    _ALIGN_C      = int(Qt.AlignCenter)
    _BTN_OK       = QDialogButtonBox.Ok
    _SCROLLBAR_ON = Qt.ScrollBarAlwaysOn
    _exec         = lambda widget: widget.exec_()   # PyQt5 uses exec_()

except ImportError:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
        QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QGroupBox,
        QPushButton, QLabel, QFileDialog, QDialog, QComboBox,
        QDialogButtonBox, QSplitter, QHeaderView, QAbstractItemView,
        QMessageBox, QAction, QTextBrowser, QSizePolicy,
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex, QMutexLocker
    from PyQt6.QtGui import QColor, QBrush, QFont, QKeySequence, QIcon

    _NO_EDIT      = QAbstractItemView.EditTrigger.NoEditTriggers
    _SEL_ROWS     = QAbstractItemView.SelectionBehavior.SelectRows
    _H_SPLIT      = Qt.Orientation.Horizontal
    _ALIGN_R      = int(Qt.AlignmentFlag.AlignRight  | Qt.AlignmentFlag.AlignVCenter)
    _ALIGN_C      = int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
    _BTN_OK       = QDialogButtonBox.StandardButton.Ok
    _SCROLLBAR_ON = Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    _exec         = lambda widget: widget.exec()    # PyQt6 uses exec()


# ══════════════════════════════════════════════════════════════════════════════
# Section 1 – CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
# Edit this section to customise the viewer without touching the logic below.

BAUD_DEFAULT = 115200

# Table columns: (name, header label, width in pixels, alignment)
# Set width=0 for the column that should stretch to fill remaining space.
COLUMNS = [
    ("t_ms",   "t_ms",   110, _ALIGN_R),
    ("dev",    "dev",     38, _ALIGN_C),
    ("type",   "type",    65, _ALIGN_C),
    ("af",     "af",      32, _ALIGN_C),
    ("hub",    "hub",     35, _ALIGN_C),
    ("dirty",  "D",       22, _ALIGN_C),
    ("info",   "info",     0, _ALIGN_R),  # stretches
    ("source", "source", 130, _ALIGN_R),
]
COL_NAME  = [c[0] for c in COLUMNS]
COL_IDX   = {c[0]: i for i, c in enumerate(COLUMNS)}

# Event types: (display label, background colour)
# Add new event types here; the filter panel will pick them up automatically.
EVENT_TYPES = {
    "TX":     ("TX  – data sent",     "#BDE0FF"),   # blue
    "RX":     ("RX  – data received", "#B5F0C0"),   # green
    "ACK_TX": ("ACK sent  >>",        "#FFD9A0"),   # orange
    "ACK_RX": ("ACK received  <<",    "#FFF4A0"),   # yellow
}

# Per-slot background tint for the device filter checkboxes (cycles if >8 slots)
SLOT_PALETTE = [
    "#D6EEFF", "#D6FFD6", "#FFE8D6", "#EED6FF",
    "#D6FFFF", "#FFD6EE", "#EEFFD6", "#FFD6D6",
]

# ── Help text (displayed in Help → Usage) ─────────────────────────────────────
# Written in HTML so it renders nicely in QTextBrowser.
# Update this string when you add features.
HELP_HTML = """
<h2>RadioBell Log Viewer — Usage</h2>

<h3>Opening data sources</h3>
<p>Use the <b>File</b> menu to load data:</p>
<ul>
  <li><b>Open log file(s) …</b> (Ctrl+O) — load one or more captured <code>.txt</code>
      log files from the <code>python/log/</code> directory.</li>
  <li><b>Connect serial port …</b> (Ctrl+P) — open a live connection to a device.
      The app sends <code>R</code> (reset) to request the startup dump and then
      streams all subsequent log lines in real time.</li>
  <li>Multiple sources can be open at the same time (files and ports mixed).
      The unified <b>t_ms</b> counter is recalculated whenever a new source is added.</li>
</ul>

<h3>Event types and colours</h3>
<table border="0" cellspacing="4" cellpadding="4">
  <tr style="background:#BDE0FF">
    <td><b>TX</b></td>
    <td>Data frame transmitted by the device (<code>TXFRAME</code>).</td></tr>
  <tr style="background:#B5F0C0">
    <td><b>RX</b></td>
    <td>Data frame received by the device (<code>RXFRAME</code>).</td></tr>
  <tr style="background:#FFD9A0">
    <td><b>ACK_TX</b></td>
    <td>Acknowledgement sent by this device
        (<code>SM_STATE_SEND_ACK</code> → <code>ACK_OK</code>).</td></tr>
  <tr style="background:#FFF4A0">
    <td><b>ACK_RX</b></td>
    <td>Acknowledgement received from another slot
        (<code>SM_STATE_ACK_RECEIVED from slot X</code>).</td></tr>
</table>

<h3>Columns</h3>
<table border="0" cellspacing="4" cellpadding="4">
  <tr><td><b>t_ms</b></td>
      <td>Unified millisecond counter. Zero = first event across <i>all</i>
          sources. Derived from the PC-side [RX] timestamps embedded in the
          log files (≈ 1 tick per ms).</td></tr>
  <tr><td><b>dev</b></td>
      <td>Slot number of the device that logged this event.</td></tr>
  <tr><td><b>type</b></td>
      <td>TX / RX / ACK_TX / ACK_RX.</td></tr>
  <tr><td><b>af</b></td>
      <td>AppliFrame slot field (sender slot encoded in the frame header).</td></tr>
  <tr><td><b>hub</b></td>
      <td>Hub counter: 0 = initial broadcast from master, &gt;0 = forwarded.</td></tr>
  <tr><td><b>D</b></td>
      <td>Dirty flag — ● means the state changed since the last frame.</td></tr>
  <tr><td><b>info</b></td>
      <td>Active key states (e.g. <code>1=BLI</code>) for data frames,
          or ACK direction for ACK events.</td></tr>
  <tr><td><b>source</b></td>
      <td>Filename or serial port name the event came from.</td></tr>
</table>

<h3>Filtering</h3>
<p>The left panel contains two filter groups:</p>
<ul>
  <li><b>Devices</b> — one checkbox per slot. Appears automatically when
      a new slot is seen in the data.</li>
  <li><b>Event type</b> — TX / RX / ACK_TX / ACK_RX. Uncheck types you
      are not interested in.</li>
</ul>
<p>Filters apply instantly without reloading the data.</p>

<h3>View menu</h3>
<ul>
  <li><b>Auto-scroll</b> — keep the last row visible as new events arrive
      (useful during live serial capture).</li>
</ul>

<h3>Command-line usage</h3>
<p><b>Wichtig:</b> Immer <code>viewer.py</code> zuerst angeben —
<code>python viewer.py log/*</code>, <b>nicht</b> <code>python log/*</code>.</p>
<pre>
  python viewer.py                          # open GUI empty
  python viewer.py log/slot_1.txt …        # pre-load files
  ./viewer.py log/*                        # shortcut (Linux/Mac)
  python viewer.py /dev/ttyUSB0            # auto-connect serial (Linux)
  python viewer.py COM3                    # auto-connect serial (Windows)
</pre>

<h3>Extending the viewer</h3>
<p>All customisable values are in <b>Section 1 – CONFIGURATION</b> at the
top of <code>viewer.py</code>:</p>
<ul>
  <li>Add a new event type in <code>EVENT_TYPES</code>.</li>
  <li>Add or reorder columns in <code>COLUMNS</code>.</li>
  <li>Change background colours in <code>EVENT_TYPES</code> or
      <code>SLOT_PALETTE</code>.</li>
</ul>
<p>The parsing logic lives in <code>parse_logs.py</code>
(<code>parse_events()</code>, <code>assign_t_ms()</code>, etc.).</p>
"""


# ══════════════════════════════════════════════════════════════════════════════
# Section 2 – PARSING BRIDGE
# ══════════════════════════════════════════════════════════════════════════════
# parse_logs.py lives in the same directory and does all the heavy lifting.
# We just import what we need here.

sys.path.insert(0, str(Path(__file__).parent))
from parse_logs import (
    parse_events,          # parse a complete list of log lines → list of events
    assign_t_ms,           # compute unified t_ms field for all events in-place
    deduplicate,           # remove (device_slot, type, tick) duplicates
    parse_anchors,         # extract (epoch_ms, tick) anchor pairs from log lines
    tick_to_epoch_ms,      # convert device tick → epoch ms using anchors
    extract_tick_msg,      # split "NNNNNNNNNN: message" → (tick, msg)
)


def event_to_row(event: dict) -> list[str]:
    """
    Convert one event dict into a list of display strings,
    one entry per column in COLUMNS.
    """
    t_ms   = f"{event.get('t_ms', 0):010d}"
    dev    = str(event['device_slot'])
    typ    = event['type']
    af     = str(event['af_slot'])  if event.get('af_slot')  is not None else ""
    hub    = str(event['hubCnt'])   if event.get('hubCnt')   is not None else ""
    dirty  = "●"                    if event.get('dirty')              else ""
    source = event.get('source_file', "")

    if typ in ("TX", "RX"):
        active_states = "  ".join(
            f"{key}={val}"
            for key, val in event.get('state', {}).items()
            if val != "OFF"
        )
        info = active_states or "—"
    elif typ == "ACK_TX":
        info = ">> ACK sent"
    else:
        info = f"<< from slot {event.get('from_slot', '?')}"

    # Return values in the same order as COLUMNS
    return [t_ms, dev, typ, af, hub, dirty, info, source]


# ══════════════════════════════════════════════════════════════════════════════
# Section 3 – SERIAL I/O
# ══════════════════════════════════════════════════════════════════════════════

class _StreamParser:
    """
    Parses RadioBell log lines one at a time (for a live serial stream).

    Call feed(line) for each incoming line.  It returns a list of complete
    events.  Multi-line blocks (TXFRAME/RXFRAME) are accumulated internally
    and emitted only when they are complete.

    This mirrors the logic in parse_logs.parse_events() but operates on a
    stream rather than a pre-loaded file.
    """

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.device_slot = None        # filled from "my_slot = X" header line
        self.anchors     = []          # (epoch_ms, device_tick) anchor pairs
        self._frame      = None        # pending multi-line frame being built
        self._labels     = None        # label row from the pending frame

    # ── internal helpers ──────────────────────────────────────────────────────

    def _epoch_ms(self, tick: int):
        return tick_to_epoch_ms(tick, self.anchors) if self.anchors else None

    def _base_event(self, tick: int, event_type: str) -> dict:
        return {
            "source_file":  self.source_name,
            "device_slot":  self.device_slot or 0,
            "type":         event_type,
            "tick":         tick,
            "_epoch_ms":    self._epoch_ms(tick),
        }

    def _flush_frame(self):
        """Return and clear the pending frame."""
        frame, self._frame, self._labels = self._frame, None, None
        return frame

    # ── public interface ──────────────────────────────────────────────────────

    def feed(self, line: str) -> list[dict]:
        """
        Feed one log line.  Returns a list of complete events (usually 0 or 1).
        """
        tick, msg = extract_tick_msg(line)
        if msg is None:
            return []

        emitted = []

        # ── Learn the device slot from the EEPROM header ──────────────────
        if self.device_slot is None:
            m = re.match(r"my_slot\s*=\s*(\d+)", msg)
            if m:
                self.device_slot = int(m.group(1))

        # ── New data frame starting ───────────────────────────────────────
        m = re.match(r"(TXFRAME|RXFRAME)\s*\(c:", msg)
        if m:
            if self._frame:                       # flush any unfinished frame
                emitted.append(self._flush_frame())
            frame = self._base_event(tick, "TX" if "TX" in m.group(1) else "RX")
            frame.update({"af_slot": None, "pl_slot": None,
                          "hubCnt": None, "state": {}, "dirty": False})
            self._frame = frame
            return emitted

        # ── Continue building the pending frame ───────────────────────────
        if self._frame is not None:
            pf = self._frame

            if (m := re.match(r"AF\s+slot\s*=\s*(\d+)", msg)):
                pf["af_slot"] = int(m.group(1));  return emitted
            if (m := re.match(r"PL\s+slot\s*=\s*(\d+)", msg)):
                pf["pl_slot"] = int(m.group(1));  return emitted
            if (m := re.match(r"hubCnt\s*=\s*(\d+)", msg)):
                pf["hubCnt"]  = int(m.group(1));  return emitted
            if msg == "state":
                return emitted
            if (m := re.match(r"label\s*=\s*(.*)", msg)):
                self._labels = m.group(1).split(); return emitted
            if (m := re.match(r"State\s*=\s*(.*)", msg)) and self._labels:
                vals = m.group(1).split()
                pf["state"] = {
                    self._labels[k].lower(): vals[k]
                    for k in range(min(len(self._labels), len(vals)))
                }
                return emitted
            if msg == "Dirty":
                pf["dirty"] = True
                emitted.append(self._flush_frame())
                return emitted
            # Any unrelated line means the frame block is done
            emitted.append(self._flush_frame())

        # ── ACK sent (bare "SM_STATE_SEND_ACK", no ">>>") ────────────────
        if re.match(r"SM_STATE_SEND_ACK\s*$", msg):
            emitted.append(self._base_event(tick, "ACK_TX"))
            return emitted

        # ── ACK received ─────────────────────────────────────────────────
        m = re.match(r"SM_STATE_ACK_RECEIVED\s+from\s+slot\s+(\d+)", msg)
        if m:
            evt = self._base_event(tick, "ACK_RX")
            evt["from_slot"] = int(m.group(1))
            emitted.append(evt)
            return emitted

        return emitted


class SerialWorker(QThread):
    """
    Background thread that reads lines from a serial port and emits events.

    Signals
    -------
    event_ready(dict)   – emitted for each complete parsed event
    status_msg(str)     – emitted for status/error messages
    """

    event_ready = pyqtSignal(dict)
    status_msg  = pyqtSignal(str)

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
            self.status_msg.emit("pyserial is not installed. Run:  pip install pyserial")
            return

        try:
            ser = serial.Serial(self._port, self._baud, timeout=1.0)
        except Exception as exc:
            self.status_msg.emit(f"Cannot open {self._port}: {exc}")
            return

        parser      = _StreamParser(self._port)
        start_epoch = int(datetime.now().timestamp() * 1000)
        anchor_set  = False

        try:
            ser.write(b"R")   # ask the device for its startup dump
        except Exception:
            pass

        while self._running:
            try:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("ascii", errors="replace").rstrip("\r\n")

                # Build the first anchor from the very first tick we see
                if not anchor_set:
                    tick, _ = extract_tick_msg(line)
                    if tick is not None:
                        parser.anchors.append((start_epoch, tick))
                        anchor_set = True

                for evt in parser.feed(line):
                    self.event_ready.emit(evt)

            except Exception as exc:
                if self._running:
                    self.status_msg.emit(f"Serial error on {self._port}: {exc}")
                break

        try:
            ser.close()
        except Exception:
            pass

        self.status_msg.emit(f"Disconnected from {self._port}")


# ══════════════════════════════════════════════════════════════════════════════
# Section 4 – DIALOGS
# ══════════════════════════════════════════════════════════════════════════════

class SerialDialog(QDialog):
    """
    Modal dialog for selecting a serial port and baud rate.
    Shows all currently available ports with their descriptions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect Serial Port")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Port selection
        port_group = QGroupBox("Serial port")
        port_layout = QVBoxLayout(port_group)

        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)      # allow typing a port manually
        port_layout.addWidget(self._port_combo)

        refresh_btn = QPushButton("Refresh port list")
        refresh_btn.clicked.connect(self._refresh_ports)
        port_layout.addWidget(refresh_btn)

        layout.addWidget(port_group)

        # Baud rate selection
        baud_group = QGroupBox("Baud rate")
        baud_layout = QHBoxLayout(baud_group)

        self._baud_combo = QComboBox()
        for baud in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600):
            self._baud_combo.addItem(str(baud))
        self._baud_combo.setCurrentText(str(BAUD_DEFAULT))
        baud_layout.addWidget(self._baud_combo)

        layout.addWidget(baud_group)

        # OK / Cancel
        buttons = QDialogButtonBox(_BTN_OK | QDialogButtonBox.Cancel
                                   if hasattr(QDialogButtonBox, 'Cancel')
                                   else _BTN_OK | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_ports()

    def _refresh_ports(self):
        self._port_combo.clear()
        try:
            import serial.tools.list_ports
            ports = sorted(serial.tools.list_ports.comports(),
                           key=lambda p: p.device)
            for p in ports:
                self._port_combo.addItem(
                    f"{p.device}  —  {p.description}",
                    userData=p.device,
                )
        except Exception:
            pass
        if self._port_combo.count() == 0:
            self._port_combo.addItem("(no ports found)")

    @property
    def port(self) -> str:
        data = self._port_combo.currentData()
        if data:
            return data
        # User may have typed a port name directly
        return self._port_combo.currentText().split()[0]

    @property
    def baud(self) -> int:
        return int(self._baud_combo.currentText())


class HelpDialog(QDialog):
    """
    Non-modal dialog showing usage instructions and feature description.
    Content is defined in HELP_HTML (Section 1 – CONFIGURATION).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RadioBell Log Viewer — Usage & Features")
        self.resize(680, 560)

        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setHtml(HELP_HTML)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)

        close_btn = QDialogButtonBox(_BTN_OK)
        close_btn.accepted.connect(self.accept)
        layout.addWidget(close_btn)


# ══════════════════════════════════════════════════════════════════════════════
# Section 5 – MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """
    Top-level application window.

    State
    -----
    self._events   – master list of all events (deduplicated, sorted by t_ms)
    self._workers  – list of running SerialWorker threads
    self._pending  – events received from serial threads, waiting to be merged
    self._mutex    – guards self._pending (accessed from worker threads)

    Flow for file input
    -------------------
      _open_files() → _load_paths() → parse_events() / assign_t_ms()
                    → _rebuild_table()

    Flow for serial input
    ---------------------
      _connect_serial() → SerialWorker.start()
                       → SerialWorker.event_ready → _on_serial_event() [thread]
                       → QTimer._flush_pending() every 250 ms [main thread]
                       → _rebuild_table()
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RadioBell Log Viewer")
        self.resize(1200, 700)

        self._events:  list[dict]          = []
        self._workers: list[SerialWorker]  = []
        self._pending: list[dict]          = []
        self._mutex    = QMutex()
        self._auto_scroll = True
        self._paused      = False

        self._build_menu_bar()
        self._build_toolbar()
        self._build_central_widget()
        self._build_status_bar()

        # Timer: move serial events from _pending into _events every 250 ms
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_pending)
        self._flush_timer.start(250)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        toolbar = self.addToolBar("Controls")
        toolbar.setMovable(False)

        self._pause_action = QAction("Pause", self)
        self._pause_action.setCheckable(True)
        self._pause_action.setShortcut(QKeySequence("Space"))
        self._pause_action.setStatusTip(
            "Pause live display (Space) — events keep accumulating in the background")
        self._pause_action.toggled.connect(self._toggle_pause)
        toolbar.addAction(self._pause_action)

    def _toggle_pause(self, paused: bool):
        self._paused = paused
        self._pause_action.setText("Resume" if paused else "Pause")
        if not paused:
            self._flush_pending()   # immediately show events that arrived while paused

    # ── Menu bar ──────────────────────────────────────────────────────────────

    def _build_menu_bar(self):
        menubar = self.menuBar()

        # ── File ──────────────────────────────────────────────────────────
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open log file(s) …", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.setStatusTip("Load one or more captured .txt log files")
        open_action.triggered.connect(self._open_files)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        connect_action = QAction("&Connect serial port …", self)
        connect_action.setShortcut(QKeySequence("Ctrl+P"))
        connect_action.setStatusTip("Connect to a live device via serial / COM port")
        connect_action.triggered.connect(self._open_serial_dialog)
        file_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect all ports", self)
        disconnect_action.setStatusTip("Stop all active serial connections")
        disconnect_action.triggered.connect(self._disconnect_all)
        file_menu.addAction(disconnect_action)

        file_menu.addSeparator()

        clear_action = QAction("C&lear all data", self)
        clear_action.setShortcut(QKeySequence("Ctrl+L"))
        clear_action.setStatusTip("Remove all events from the table")
        clear_action.triggered.connect(self._clear)
        file_menu.addAction(clear_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # ── View ──────────────────────────────────────────────────────────
        view_menu = menubar.addMenu("&View")

        self._auto_scroll_action = QAction("&Auto-scroll to latest event", self)
        self._auto_scroll_action.setCheckable(True)
        self._auto_scroll_action.setChecked(True)
        self._auto_scroll_action.setStatusTip(
            "Keep the most recent event visible (useful during live capture)")
        self._auto_scroll_action.toggled.connect(
            lambda checked: setattr(self, "_auto_scroll", checked))
        view_menu.addAction(self._auto_scroll_action)

        # ── Help ──────────────────────────────────────────────────────────
        help_menu = menubar.addMenu("&Help")

        usage_action = QAction("&Usage / Features …", self)
        usage_action.setShortcut(QKeySequence("F1"))
        usage_action.setStatusTip("Show usage instructions and feature overview")
        usage_action.triggered.connect(self._show_help)
        help_menu.addAction(usage_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ── Central widget: filter panel + event table ────────────────────────────

    def _build_central_widget(self):
        splitter = QSplitter(_H_SPLIT)

        splitter.addWidget(self._build_filter_panel())
        splitter.addWidget(self._build_event_table())
        splitter.setStretchFactor(1, 1)   # table takes all extra space

        self.setCentralWidget(splitter)

    def _build_filter_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(190)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(6)

        # Device filter (populated dynamically when events are loaded)
        self._device_group  = QGroupBox("Devices")
        self._device_layout = QVBoxLayout(self._device_group)
        self._device_layout.setSpacing(3)
        self._device_checks: dict[int, QCheckBox] = {}
        layout.addWidget(self._device_group)

        # Event-type filter
        type_group  = QGroupBox("Event type")
        type_layout = QVBoxLayout(type_group)
        type_layout.setSpacing(3)
        self._type_checks: dict[str, QCheckBox] = {}
        for event_type, (label, colour) in EVENT_TYPES.items():
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setStyleSheet(
                f"QCheckBox {{ background: {colour}; padding: 2px 5px;"
                f"             border-radius: 3px; }}"
            )
            cb.stateChanged.connect(self._apply_filter)
            self._type_checks[event_type] = cb
            type_layout.addWidget(cb)
        layout.addWidget(type_group)

        layout.addStretch()

        # Legend
        legend_group  = QGroupBox("Legende")
        legend_layout = QVBoxLayout(legend_group)
        legend_layout.setSpacing(3)

        def _swatch_row(colour: str, text: str) -> QWidget:
            row    = QWidget()
            hbox   = QHBoxLayout(row)
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.setSpacing(5)
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(
                f"background: {colour}; border: 1px solid #888; border-radius: 2px;")
            hbox.addWidget(swatch)
            hbox.addWidget(QLabel(text))
            hbox.addStretch()
            return row

        for _, (label, colour) in EVENT_TYPES.items():
            legend_layout.addWidget(_swatch_row(colour, label.split("–")[0].strip()))

        dev_label = QLabel("dev = Slot-Farbe")
        dev_label.setStyleSheet("font-size: 8pt; color: #555;")
        legend_layout.addWidget(dev_label)

        layout.addWidget(legend_group)

        # Active sources list
        sources_group = QGroupBox("Active sources")
        sources_vbox  = QVBoxLayout(sources_group)
        self._sources_label = QLabel("—")
        self._sources_label.setWordWrap(True)
        self._sources_label.setStyleSheet("font-size: 8pt;")
        sources_vbox.addWidget(self._sources_label)
        layout.addWidget(sources_group)

        return panel

    def _build_event_table(self) -> QTableWidget:
        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels([col[1] for col in COLUMNS])
        self._table.setEditTriggers(_NO_EDIT)
        self._table.setSelectionBehavior(_SEL_ROWS)
        self._table.setAlternatingRowColors(False)
        self._table.setSortingEnabled(False)
        self._table.verticalHeader().setDefaultSectionSize(22)
        self._table.verticalHeader().setVisible(False)
        self._table.setVerticalScrollBarPolicy(_SCROLLBAR_ON)
        self._table.setFont(
            QFont("Consolas", 9) if sys.platform == "win32"
            else QFont("Monospace", 9)
        )

        header = self._table.horizontalHeader()
        for col_idx, (_, _, width, _) in enumerate(COLUMNS):
            if width == 0:
                header.setSectionResizeMode(
                    col_idx,
                    QHeaderView.ResizeMode.Stretch
                    if hasattr(QHeaderView, "ResizeMode")
                    else QHeaderView.Stretch,
                )
            else:
                self._table.setColumnWidth(col_idx, width)

        return self._table

    def _build_status_bar(self):
        self._status_label = QLabel("No data loaded.")
        self.statusBar().addWidget(self._status_label)

    # ── File actions ──────────────────────────────────────────────────────────

    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open log file(s)",
            str(Path(__file__).parent / "log"),
            "Log files (*.txt);;All files (*)",
        )
        self._load_paths([Path(p) for p in paths])

    def _load_paths(self, paths: list):
        new_events = []
        for path in paths:
            if not path.is_file():
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            new_events.extend(parse_events(path.name, lines))

        if not new_events:
            return

        combined = deduplicate(self._events + new_events)
        assign_t_ms(combined)
        combined.sort(key=lambda e: e.get("t_ms", 0))
        self._events = combined
        self._rebuild_table()

    # ── Serial actions ────────────────────────────────────────────────────────

    def _open_serial_dialog(self):
        dialog = SerialDialog(self)
        if not _exec(dialog):
            return
        self._connect_serial(dialog.port, dialog.baud)

    def _connect_serial(self, port: str, baud: int = BAUD_DEFAULT):
        worker = SerialWorker(port, baud)
        worker.event_ready.connect(self._on_serial_event)
        worker.status_msg.connect(
            lambda msg: self.statusBar().showMessage(msg, 5000))
        self._workers.append(worker)
        worker.start()
        self.statusBar().showMessage(f"Connected to {port} at {baud} baud", 4000)

    def _disconnect_all(self):
        for worker in self._workers:
            worker.stop()
            worker.wait(1500)
        self._workers.clear()
        self.statusBar().showMessage("All serial ports disconnected.", 3000)

    def _on_serial_event(self, event: dict):
        """Called from SerialWorker thread — only touches _pending (mutex-protected)."""
        with QMutexLocker(self._mutex):
            self._pending.append(event)

    def _flush_pending(self):
        """Called by timer in the main thread every 250 ms."""
        if self._paused:
            return
        with QMutexLocker(self._mutex):
            if not self._pending:
                return
            batch          = self._pending[:]
            self._pending  = []

        combined = deduplicate(self._events + batch)
        assign_t_ms(combined)
        combined.sort(key=lambda e: e.get("t_ms", 0))

        if len(combined) == len(self._events):
            return   # all duplicates — nothing to update

        self._events = combined
        self._rebuild_table()

    # ── Table management ──────────────────────────────────────────────────────

    def _rebuild_table(self):
        """Repopulate the table from scratch using self._events."""
        self._table.setRowCount(0)

        # Add a device checkbox for every new slot we haven't seen before
        slots = sorted({
            e["device_slot"] for e in self._events
            if e["device_slot"] is not None
        })
        for slot in slots:
            if slot not in self._device_checks:
                colour = SLOT_PALETTE[slot % len(SLOT_PALETTE)]
                cb = QCheckBox(f"Slot {slot}")
                cb.setChecked(True)
                cb.setStyleSheet(
                    f"QCheckBox {{ background: {colour}; padding: 2px 5px;"
                    f"             border-radius: 3px; }}"
                )
                cb.stateChanged.connect(self._apply_filter)
                self._device_checks[slot] = cb
                self._device_layout.addWidget(cb)

        active_types   = {t for t, cb in self._type_checks.items()  if cb.isChecked()}
        active_devices = {s for s, cb in self._device_checks.items() if cb.isChecked()}

        for event in self._events:
            visible = (
                event["type"] in active_types
                and event.get("device_slot") in active_devices
            )
            self._insert_row(event, visible)

        self._update_status()

        if self._auto_scroll:
            self._table.scrollToBottom()

        # Update sources list
        source_names = sorted({e["source_file"] for e in self._events})
        self._sources_label.setText("\n".join(source_names) or "—")

    def _insert_row(self, event: dict, visible: bool = True):
        """Append one row to the table."""
        background = QBrush(QColor(EVENT_TYPES.get(event["type"], ("", "#FFFFFF"))[1]))
        slot = event.get("device_slot")
        slot_brush = (QBrush(QColor(SLOT_PALETTE[slot % len(SLOT_PALETTE)]))
                      if slot is not None else background)
        row_values = event_to_row(event)
        dev_col    = COL_IDX["dev"]

        row = self._table.rowCount()
        self._table.insertRow(row)

        for col_idx, (col_name, _, _, alignment) in enumerate(COLUMNS):
            item = QTableWidgetItem(row_values[col_idx])
            item.setBackground(slot_brush if col_idx == dev_col else background)
            item.setTextAlignment(alignment)
            self._table.setItem(row, col_idx, item)

        if not visible:
            self._table.setRowHidden(row, True)

    def _apply_filter(self):
        """Show/hide rows without rebuilding the table."""
        active_types   = {t for t, cb in self._type_checks.items()  if cb.isChecked()}
        active_devices = {s for s, cb in self._device_checks.items() if cb.isChecked()}

        type_col = COL_IDX["type"]
        dev_col  = COL_IDX["dev"]

        for row in range(self._table.rowCount()):
            type_item = self._table.item(row, type_col)
            dev_item  = self._table.item(row, dev_col)
            if type_item is None or dev_item is None:
                continue
            event_type = type_item.text()
            dev_text   = dev_item.text()
            visible = (
                event_type in active_types
                and dev_text.isdigit()
                and int(dev_text) in active_devices
            )
            self._table.setRowHidden(row, not visible)

        self._update_status()

    def _update_status(self):
        total = len(self._events)
        shown = sum(1 for r in range(self._table.rowCount())
                    if not self._table.isRowHidden(r))
        by_type = {t: sum(1 for e in self._events if e["type"] == t)
                   for t in EVENT_TYPES}
        slots   = sorted({e["device_slot"] for e in self._events
                          if e["device_slot"] is not None})
        self._status_label.setText(
            f"{total} events  "
            f"({by_type['TX']} TX  {by_type['RX']} RX  "
            f"{by_type['ACK_TX']} ACK>  {by_type['ACK_RX']} ACK<)  │  "
            f"{shown} visible  │  "
            f"slots: {', '.join(str(s) for s in slots) or '—'}"
        )

    def _clear(self):
        self._events.clear()
        self._table.setRowCount(0)
        for cb in list(self._device_checks.values()):
            self._device_layout.removeWidget(cb)
            cb.deleteLater()
        self._device_checks.clear()
        self._sources_label.setText("—")
        self._status_label.setText("No data loaded.")

    # ── Help actions ──────────────────────────────────────────────────────────

    def _show_help(self):
        dialog = HelpDialog(self)
        _exec(dialog)

    def _show_about(self):
        QMessageBox.about(
            self,
            "About RadioBell Log Viewer",
            "<b>RadioBell Log Viewer</b><br><br>"
            "Displays the event timeline of RadioBell devices<br>"
            "from captured log files or live serial connections.<br><br>"
            "Sources:<br>"
            "&nbsp;&nbsp;<code>viewer.py</code> — GUI application<br>"
            "&nbsp;&nbsp;<code>parse_logs.py</code> — parsing logic<br><br>"
            "Press <b>F1</b> or use <b>Help → Usage / Features</b> for details.",
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Stop all serial threads cleanly before exiting."""
        self._disconnect_all()
        event.accept()


# ══════════════════════════════════════════════════════════════════════════════
# Section 6 – ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    import os
    # Force X11 backend so setWindowIcon() works on KDE Wayland (XWayland).
    # Without this the Wayland compositor ignores the icon entirely.
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland*=false;kf.service*=false"

    app = QApplication(sys.argv)
    app.setApplicationName("RadioBell Log Viewer")
    app.setStyle("Fusion")   # consistent look on Windows and Linux

    icon_path = Path(__file__).resolve().parent / "viewer_icon.png"
    icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    app.setWindowIcon(icon)

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()

    # Handle command-line arguments:
    #   .txt files → load immediately
    #   anything else → try as a serial port name
    if len(sys.argv) > 1:
        files = [Path(a) for a in sys.argv[1:] if a.endswith(".txt")]
        ports = [a for a in sys.argv[1:] if not a.endswith(".txt")]
        if files:
            window._load_paths(files)
        for port in ports:
            window._connect_serial(port)

    try:
        sys.exit(app.exec())
    except AttributeError:
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()
