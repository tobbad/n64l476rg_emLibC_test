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

import html
import sys
import re
import json
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
        QMessageBox, QAction, QTextBrowser, QListWidget, QTextEdit,
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex, QMutexLocker
    from PyQt5.QtGui import QColor, QBrush, QFont, QKeySequence, QIcon

    _NO_EDIT      = QAbstractItemView.NoEditTriggers
    _SEL_ROWS     = QAbstractItemView.SelectRows
    _H_SPLIT      = Qt.Horizontal
    _V_SPLIT      = Qt.Vertical
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
        QMessageBox, QAction, QTextBrowser, QListWidget, QTextEdit,
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex, QMutexLocker
    from PyQt6.QtGui import QColor, QBrush, QFont, QKeySequence, QIcon

    _NO_EDIT      = QAbstractItemView.EditTrigger.NoEditTriggers
    _SEL_ROWS     = QAbstractItemView.SelectionBehavior.SelectRows
    _H_SPLIT      = Qt.Orientation.Horizontal
    _V_SPLIT      = Qt.Orientation.Vertical
    _ALIGN_R      = int(Qt.AlignmentFlag.AlignRight  | Qt.AlignmentFlag.AlignVCenter)
    _ALIGN_C      = int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
    _BTN_OK       = QDialogButtonBox.StandardButton.Ok
    _SCROLLBAR_ON = Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    _exec         = lambda widget: widget.exec()    # PyQt6 uses exec()


# ══════════════════════════════════════════════════════════════════════════════
# Section 1 – CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
# Edit this section to customise the viewer without touching the logic below.

BAUD_DEFAULT      = 115200
_MAX_CONSOLE_LINES = 500   # keep at most this many lines in the raw console

# Table columns: (name, header label, width in pixels, alignment)
# Set width=0 for the column that should stretch to fill remaining space.
COLUMNS = [
    ("t_ms",    "t_ms",    110, _ALIGN_R),
    ("slot",    "slot",     38, _ALIGN_C),
    ("type",    "type",     65, _ALIGN_C),
    ("hub",     "hub",      35, _ALIGN_C),
    ("cycle",   "cyc",      48, _ALIGN_R),   # radio cycle counter (360 ms per cycle)
    ("af",      "af",       32, _ALIGN_C),   # sender slot (af_slot)
    ("pl",      "pl",       32, _ALIGN_C),   # button-press slot (pl_slot)
    ("subslot", "sub",      28, _ALIGN_C),   # subslot within slot (2.8 ms resolution)
    ("dirty",   "D",        22, _ALIGN_C),
    ("info",    "info",      0, _ALIGN_R),   # stretches
]
# Source is stored as UserRole data on column 0 (not displayed as a column)
_SOURCE_ROLE = 256  # Qt.UserRole
COL_IDX = {c[0]: i for i, c in enumerate(COLUMNS)}

# Event types: (display label, background colour)
# Add new event types here; the filter panel will pick them up automatically.
EVENT_TYPES = {
    "TX":      ("TX   – data sent",             "#BDE0FF"),   # blue
    "RX":      ("RX   – data received",         "#B5F0C0"),   # green
    "ACK_TX":  ("ACK  sent  >>",                "#FFD9A0"),   # orange
    "ACK_RX":  ("ACK  received  <<",            "#FFF4A0"),   # yellow
    "KA_TX":   ("KA   – keep-alive sent >>",    "#E8D0FF"),   # light purple
    "KA_RX":   ("KA   – keep-alive recv <<",    "#F5E8FF"),   # lighter purple
    "DATA_RX": ("DATA – radio bytes received",  "#D0EED0"),   # pale green
}

# Per-slot colours — 8 vivid, clearly distinct hues.
# Mapped via slot_color(slot) using slot//2 so the 8 odd slots 1,3,5,…,15
# each get a unique colour without collision.
SLOT_PALETTE = [
    "#E03030",  # 0 → rot          (slot  1)   0°
    "#E07820",  # 1 → orange       (slot  3)   28°
    "#C8B010",  # 2 → gelb         (slot  5)   52°
    "#28B028",  # 3 → grün         (slot  7)   120°
    "#2060D0",  # 4 → blau         (slot  9)   225°
    "#B000B0",  # 5 → violett      (slot 11)   300°
    "#D02878",  # 6 → rosa         (slot 13)   330°
    "#202020",  # 7 → schwarz      (slot 15)
]

def slot_color(slot: int) -> str:
    """Map a slot number to a palette colour (slot//2 avoids collisions for odd slots)."""
    if slot < 0:
        return "#888888"   # grau für unbekannte Slots
    return SLOT_PALETTE[(slot // 2) % len(SLOT_PALETTE)]


# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).resolve().parent / "rbconfig.json"

def load_config(path: Path) -> dict:
    """Load rbconfig.json; return empty dict on missing file or parse error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        print(f"Warning: could not load {path}: {exc}", file=sys.stderr)
        return {}

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
    <td>Data frame transmitted (<code>TXFRAME:</code> block).</td></tr>
  <tr style="background:#B5F0C0">
    <td><b>RX</b></td>
    <td>Data frame received (<code>RXFRAME:</code> block).</td></tr>
  <tr style="background:#FFD9A0">
    <td><b>ACK_TX</b></td>
    <td>ACK sent (<code>rb_system.txFrame-&gt;Cmd = ACK_OK</code>).</td></tr>
  <tr style="background:#FFF4A0">
    <td><b>ACK_RX</b></td>
    <td>ACK received (<code>SM_STATE_ACK_RECEIVED from slot X</code>).</td></tr>
  <tr style="background:#E8D0FF">
    <td><b>KA_TX</b></td>
    <td>Keep-alive sent (<code>Send SM_STATE_KEEP_ALIVE</code>).</td></tr>
  <tr style="background:#F5E8FF">
    <td><b>KA_RX</b></td>
    <td>Keep-alive received (<code>SM_STATE_KEEP_ALIVE</code>).</td></tr>
  <tr style="background:#D0EED0">
    <td><b>DATA_RX</b></td>
    <td>Radio bytes received (<code>SM_STATE_DATA_RECEIVED</code>).</td></tr>
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
  <tr><td><b>cyc</b></td>
      <td>Radio cycle counter — one cycle = 16 slots × 22.5 ms = <b>360 ms</b>.</td></tr>
  <tr><td><b>sub</b></td>
      <td>Subslot within the slot (0–7) — resolution 22.5 ms / 8 = <b>2.8 ms</b>.</td></tr>
  <tr><td><b>af</b></td>
      <td>Sender slot (AF slot) — which device sent this frame.</td></tr>
  <tr><td><b>pl</b></td>
      <td>Button-press slot (PL slot) — which device originally pressed the button.</td></tr>
  <tr><td><b>hub</b></td>
      <td>Hub counter: 0 = initial broadcast from master, &gt;0 = forwarded.</td></tr>
  <tr><td><b>D</b></td>
      <td>Dirty flag — ● means the state changed since the last frame.</td></tr>
  <tr><td><b>info</b></td>
      <td>Active key states (e.g. <code>1=BLI</code>) for data frames,
          or ACK direction for ACK events.</td></tr>
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
    parse_events,      # parse a complete list of log lines → list of events
    assign_t_ms,       # compute unified t_ms field for all events in-place
    deduplicate,       # remove (device_slot, type, tick) duplicates
    tick_to_epoch_ms,  # convert device tick → epoch ms using anchors
    extract_tick_msg,  # split "NNNNNNNNNN: message" → (tick, msg)
)


def normalize_cycles(events: list) -> None:
    """Shift cycle values per device so each device's first seen cycle becomes 0."""
    device_min: dict = {}
    for e in events:
        if e.get('cycle') is not None:
            slot = e.get('device_slot')
            c = e['cycle']
            if slot not in device_min or c < device_min[slot]:
                device_min[slot] = c
    for e in events:
        if e.get('cycle') is not None:
            slot = e.get('device_slot')
            e['cycle'] -= device_min.get(slot, 0)


def event_to_row(event: dict) -> list[str]:
    """
    Convert one event dict into a list of display strings,
    one entry per column in COLUMNS.
    """
    t_ms    = f"{event.get('t_ms', 0):010d}"
    dev     = str(event['device_slot'])
    typ     = event['type']
    cycle   = str(event['cycle'])   if event.get('cycle')   is not None else ""
    subslot = str(event['subslot']) if event.get('subslot') is not None else ""
    af      = str(event['af_slot']) if event.get('af_slot') is not None else ""
    pl      = str(event['pl_slot']) if event.get('pl_slot') is not None else ""
    hub     = str(event['hubCnt'])  if event.get('hubCnt')  is not None else ""
    dirty   = "●"                   if event.get('dirty')               else ""

    if typ in ("TX", "RX"):
        active_states = "  ".join(
            f"{key}={val}"
            for key, val in event.get('state', {}).items()
            if val != "OFF"
        )
        info = active_states or "—"
    elif typ == "ACK_TX":
        info = ">> ACK sent"
    elif typ == "ACK_RX":
        info = f"<< from slot {event.get('from_slot', '?')}"
    elif typ == "KA_TX":
        info = ">> KA sent"
    elif typ == "KA_RX":
        info = "<< KA received"
    else:  # DATA_RX
        info = event.get("info", "radio bytes received")

    # Return values in the same order as COLUMNS (source stored separately as UserRole)
    return [t_ms, dev, typ, hub, cycle, af, pl, subslot, dirty, info]


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

    def __init__(self, source_name: str, device_slot=None):
        self.source_name = source_name
        self.device_slot = device_slot  # pre-set from config; overwritten by "my_slot = X"
        self.anchors     = []           # (epoch_ms, device_tick) anchor pairs
        self._frame      = None         # pending multi-line frame being built
        self._labels     = None         # label row from the pending frame
        self._slot_seen  = False        # True after first my_slot line; second = reset

    # ── internal helpers ──────────────────────────────────────────────────────

    def _epoch_ms(self, tick: int):
        return tick_to_epoch_ms(tick, self.anchors) if self.anchors else None

    def _base_event(self, tick: int, event_type: str) -> dict:
        return {
            "source_file":  self.source_name,
            "device_slot":  self.device_slot if self.device_slot is not None else -1,
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

        # ── Learn the device slot from the EEPROM header (always authoritative) ─
        m = re.match(r"my_slot\s*=\s*(\d+)", msg)
        if m:
            new_slot = int(m.group(1))
            if self._slot_seen:
                # Second occurrence → device has been reset; signal the main thread
                self.anchors.clear()   # SerialWorker will set a fresh anchor
                emitted.append({
                    "type":        "_RESET_",
                    "source_file": self.source_name,
                    "device_slot": new_slot,
                    "_epoch_ms":   None,
                })
            self.device_slot = new_slot
            self._slot_seen  = True

        # ── New data frame starting ───────────────────────────────────────
        m = re.match(r"(TXFRAME|RXFRAME):?\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)", msg)
        if m:
            if self._frame:                       # flush any unfinished frame
                emitted.append(self._flush_frame())
            frame = self._base_event(tick, "TX" if "TX" in m.group(1) else "RX")
            frame.update({
                "cycle":   int(m.group(2)),
                "af_slot": int(m.group(3)),   # sender slot (= af_slot)
                "subslot": int(m.group(4)),   # subslot within the slot
                "pl_slot": None,
                "hubCnt":  None,
                "state":   {},
                "dirty":   False,
            })
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

        # ── ACK sent: rb_system.txFrame->Cmd = ACK_OK (c: cycle, slot, subslot) ─
        m = re.match(
            r"rb_system\.txFrame->Cmd\s*=\s*ACK_OK\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)", msg)
        if m:
            evt = self._base_event(tick, "ACK_TX")
            evt.update({
                "cycle":   int(m.group(1)),
                "af_slot": int(m.group(2)),
                "subslot": int(m.group(3)),
            })
            emitted.append(evt)
            return emitted

        # ── ACK received: SM_STATE_ACK_RECEIVED from slot X (c: cycle, slot, subslot) ─
        m = re.match(
            r"SM_STATE_ACK_RECEIVED\s+from\s+slot\s+(\d+)\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)", msg)
        if m:
            evt = self._base_event(tick, "ACK_RX")
            evt.update({
                "from_slot": int(m.group(1)),
                "af_slot":   int(m.group(1)),
                "cycle":     int(m.group(2)),
                "subslot":   int(m.group(4)),
            })
            emitted.append(evt)
            return emitted

        # ── KEEP_ALIVE sent: Send SM_STATE_KEEP_ALIVE (c: cycle, slot, subslot) ─
        m = re.match(
            r"Send\s+SM_STATE_KEEP_ALIVE\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)", msg)
        if m:
            evt = self._base_event(tick, "KA_TX")
            evt.update({
                "cycle":   int(m.group(1)),
                "af_slot": int(m.group(2)),
                "subslot": int(m.group(3)),
            })
            emitted.append(evt)
            return emitted

        # ── KEEP_ALIVE received: SM_STATE_KEEP_ALIVE (c: cycle, slot, subslot) ─
        m = re.match(
            r"SM_STATE_KEEP_ALIVE\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)", msg)
        if m:
            evt = self._base_event(tick, "KA_RX")
            evt.update({
                "cycle":   int(m.group(1)),
                "af_slot": int(m.group(2)),
                "subslot": int(m.group(3)),
            })
            emitted.append(evt)
            return emitted

        # ── Radio bytes received: SM_STATE_DATA_RECEIVED N Bytes (from slot = X) ─
        m = re.match(
            r"SM_STATE_DATA_RECEIVED\s+(\d+)\s+Bytes\s+\(from\s+slot\s*=\s*(\d+)\)", msg)
        if m:
            evt = self._base_event(tick, "DATA_RX")
            evt.update({
                "af_slot": int(m.group(2)),
                "info":    f"{m.group(1)} B from slot {m.group(2)}",
            })
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
    raw_line    = pyqtSignal(str, str, int)  # (port, line, n_events_produced)

    def __init__(self, port: str, baud: int = BAUD_DEFAULT, device_slot=None):
        super().__init__()
        self._port        = port
        self._baud        = baud
        self._running     = True
        self._device_slot = device_slot
        self.lines_rx     = 0    # total raw lines received; read by main thread
        self.open_error   = ""   # set on open failure; read by main thread
        self.last_line    = ""   # most recent raw line; read by main thread

    def stop(self):
        self._running = False

    def run(self):
        try:
            import serial
        except ImportError:
            msg = "pyserial not installed — run: pip install pyserial"
            self.open_error = msg
            self.status_msg.emit(msg)
            return

        try:
            ser = serial.Serial(self._port, self._baud, timeout=1.0)
        except Exception as exc:
            msg = f"Cannot open {self._port}: {exc}"
            self.open_error = msg
            self.status_msg.emit(msg)
            return

        parser      = _StreamParser(self._port, self._device_slot)
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
                self.lines_rx += 1
                self.last_line = line

                # Build the first anchor from the very first tick we see
                if not anchor_set:
                    tick, _ = extract_tick_msg(line)
                    if tick is not None:
                        parser.anchors.append((start_epoch, tick))
                        anchor_set = True

                evts = parser.feed(line)
                self.raw_line.emit(self._port, line, len(evts))
                for evt in evts:
                    if evt.get("type") == "_RESET_":
                        # Device restarted: reset anchor so next tick builds a fresh one
                        anchor_set  = False
                        start_epoch = int(datetime.now().timestamp() * 1000)
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


class ConfigDialog(QDialog):
    """
    Shown on startup when no sources are configured (empty rbconfig.json).
    Lets the user define serial ports and log files, then saves the result.
    Also usable from the File menu at any time.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure sources")
        self.setMinimumWidth(480)
        self.resize(520, 360)

        layout = QVBoxLayout(self)

        # ── Serial ports ──────────────────────────────────────────────────
        port_group  = QGroupBox("Serial ports  (port → slot mapping from rbconfig.json)")
        port_vbox   = QVBoxLayout(port_group)
        self._port_list = QListWidget()
        self._port_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection
                                         if hasattr(QAbstractItemView, "SelectionMode")
                                         else QAbstractItemView.SingleSelection)
        port_vbox.addWidget(self._port_list)
        port_btn_row = QHBoxLayout()
        add_port_btn = QPushButton("Add port …")
        add_port_btn.clicked.connect(self._add_port)
        self._rm_port_btn = QPushButton("Remove")
        self._rm_port_btn.clicked.connect(self._remove_port)
        port_btn_row.addWidget(add_port_btn)
        port_btn_row.addWidget(self._rm_port_btn)
        port_btn_row.addStretch()
        port_vbox.addLayout(port_btn_row)
        layout.addWidget(port_group)

        # ── Log files ─────────────────────────────────────────────────────
        file_group = QGroupBox("Log files")
        file_vbox  = QVBoxLayout(file_group)
        self._file_list = QListWidget()
        file_vbox.addWidget(self._file_list)
        file_btn_row = QHBoxLayout()
        add_file_btn = QPushButton("Add file …")
        add_file_btn.clicked.connect(self._add_file)
        self._rm_file_btn = QPushButton("Remove")
        self._rm_file_btn.clicked.connect(self._remove_file)
        file_btn_row.addWidget(add_file_btn)
        file_btn_row.addWidget(self._rm_file_btn)
        file_btn_row.addStretch()
        file_vbox.addLayout(file_btn_row)
        layout.addWidget(file_group)

        # ── Buttons ───────────────────────────────────────────────────────
        btns = QDialogButtonBox(_BTN_OK | QDialogButtonBox.Cancel
                                if hasattr(QDialogButtonBox, 'Cancel')
                                else _BTN_OK | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Track (port, baud) pairs — list widget shows the label, this is the data
        self._port_entries: list[tuple[str, int]] = []

    def _add_port(self):
        dlg = SerialDialog(self)
        if not _exec(dlg):
            return
        port, baud = dlg.port, dlg.baud
        if any(p == port for p, _ in self._port_entries):
            return   # already listed
        self._port_entries.append((port, baud))
        self._port_list.addItem(
            f"{port}   @  {baud} baud" if baud != BAUD_DEFAULT else port)

    def _remove_port(self):
        row = self._port_list.currentRow()
        if row >= 0:
            self._port_list.takeItem(row)
            del self._port_entries[row]

    def _add_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add log file(s)",
            str(Path(__file__).parent / "log"),
            "Log files (*.txt);;All files (*)",
        )
        for p in paths:
            if not any(self._file_list.item(i).text() == p
                       for i in range(self._file_list.count())):
                self._file_list.addItem(p)

    def _remove_file(self):
        row = self._file_list.currentRow()
        if row >= 0:
            self._file_list.takeItem(row)

    @property
    def port_entries(self) -> list[tuple[str, int]]:
        return list(self._port_entries)

    @property
    def log_file_paths(self) -> list[str]:
        return [self._file_list.item(i).text()
                for i in range(self._file_list.count())]

    def populate_from_config(self, config: dict) -> None:
        """Pre-fill the dialog from an existing rbconfig dict."""
        for port, slot in config.get("port_map", {}).items():
            self._port_entries.append((port, BAUD_DEFAULT))
            label = port + (f"  (slot {slot})" if slot is not None else "")
            self._port_list.addItem(label)
        base = CONFIG_PATH.parent
        for rel in config.get("log_files", []):
            full = str((base / rel).resolve())
            self._file_list.addItem(full)


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
        self._config      = load_config(CONFIG_PATH)
        self._source_slots: dict           = {}   # source_name → confirmed device_slot
        self._session_ports: dict[str, int] = {}  # port → baud  (all ports connected this session)
        self._session_files: list[Path]    = []   # full paths of all files loaded this session

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
        if paused:
            self._rx_label.setStyleSheet(
                "color: white; background: #C03030; font-weight: bold;"
                " padding: 1px 6px; border-radius: 3px;")
            self._rx_label.setText("⏸ PAUSED")
        else:
            self._rx_label.setStyleSheet("color: #444; font-size: 8pt;")
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

        cfg_src_action = QAction("Con&figure sources …", self)
        cfg_src_action.setShortcut(QKeySequence("Ctrl+G"))
        cfg_src_action.setStatusTip(
            "Add/remove serial ports and log files, save to rbconfig.json")
        cfg_src_action.triggered.connect(self._open_config_dialog)
        file_menu.addAction(cfg_src_action)

        file_menu.addSeparator()

        connect_action = QAction("&Connect serial port …", self)
        connect_action.setShortcut(QKeySequence("Ctrl+P"))
        connect_action.setStatusTip("Connect to a live device via serial / COM port")
        connect_action.triggered.connect(self._open_serial_dialog)
        file_menu.addAction(connect_action)

        connect_cfg_action = QAction("Connect &configured ports", self)
        connect_cfg_action.setShortcut(QKeySequence("Ctrl+K"))
        connect_cfg_action.setStatusTip(
            "Connect all ports listed in port_map in rbconfig.json")
        connect_cfg_action.triggered.connect(self._connect_configured_ports)
        file_menu.addAction(connect_cfg_action)

        disconnect_action = QAction("&Disconnect all ports", self)
        disconnect_action.setStatusTip("Stop all active serial connections")
        disconnect_action.triggered.connect(self._disconnect_all)
        file_menu.addAction(disconnect_action)

        load_cfg_action = QAction("Load configured &files", self)
        load_cfg_action.setStatusTip(
            "Load all files listed in log_files in rbconfig.json")
        load_cfg_action.triggered.connect(self._load_configured_files)
        file_menu.addAction(load_cfg_action)

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
        top = QSplitter(_H_SPLIT)
        top.addWidget(self._build_filter_panel())
        top.addWidget(self._build_event_table())
        top.setStretchFactor(1, 1)

        outer = QSplitter(_V_SPLIT)
        outer.addWidget(top)
        outer.addWidget(self._build_console())
        outer.setStretchFactor(0, 4)   # table area gets 4×, console 1×
        outer.setSizes([560, 140])

        self.setCentralWidget(outer)

    def _build_console(self) -> QWidget:
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(2)
        label = QLabel("Serial console (raw output)")
        label.setStyleSheet("font-size: 8pt; color: #555;")
        vbox.addWidget(label)
        self._console = QTextEdit()
        self._console.setReadOnly(True)
        self._console.setFont(
            QFont("Consolas", 8) if sys.platform == "win32"
            else QFont("Monospace", 8))
        self._console.setStyleSheet(
            "background: #1E1E1E; color: #D4D4D4; border: none;")
        self._console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap
                                      if hasattr(QTextEdit, "LineWrapMode")
                                      else QTextEdit.NoWrap)
        vbox.addWidget(self._console)
        return container

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

        # Legend — dynamic slot colours
        legend_group        = QGroupBox("Legende")
        self._legend_layout = QVBoxLayout(legend_group)
        self._legend_layout.setSpacing(3)
        self._legend_slot_widgets: dict[int, QWidget] = {}
        layout.addWidget(legend_group)

        # Source filter (one row per connected port / loaded file)
        self._source_group  = QGroupBox("Sources")
        self._source_layout = QVBoxLayout(self._source_group)
        self._source_layout.setSpacing(2)
        self._source_checks: dict[str, QCheckBox] = {}
        self._source_rows:   dict[str, QWidget]   = {}
        layout.addWidget(self._source_group)

        return panel

    @staticmethod
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

    def _ensure_source_checkbox(self, source_name: str) -> None:
        """Add a source row (checkbox + Solo button) if not already present."""
        if source_name in self._source_checks:
            return
        short = Path(source_name).name  # show basename; full path on tooltip
        cb = QCheckBox(short)
        cb.setToolTip(source_name)
        cb.setChecked(True)
        cb.setStyleSheet("QCheckBox { font-size: 8pt; padding: 1px 3px; }")
        cb.stateChanged.connect(self._apply_filter)
        self._source_checks[source_name] = cb

        solo_btn = QPushButton("◎")
        solo_btn.setFixedSize(20, 18)
        solo_btn.setToolTip(f"Show only: {source_name}")
        solo_btn.setStyleSheet("font-size: 8pt; padding: 0;")
        solo_btn.clicked.connect(lambda _checked, sn=source_name: self._solo_source(sn))

        row = QWidget()
        hbox = QHBoxLayout(row)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(2)
        hbox.addWidget(cb, 1)
        hbox.addWidget(solo_btn, 0)
        self._source_rows[source_name] = row
        self._source_layout.addWidget(row)

    def _solo_source(self, source_name: str) -> None:
        """Check only *source_name*, uncheck all others, then apply filter."""
        for sn, cb in self._source_checks.items():
            cb.blockSignals(True)
            cb.setChecked(sn == source_name)
            cb.blockSignals(False)
        self._apply_filter()

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
        self.statusBar().addWidget(self._status_label, 1)
        self._rx_label = QLabel("")
        self._rx_label.setStyleSheet("color: #444; font-size: 8pt;")
        self.statusBar().addPermanentWidget(self._rx_label)

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
            self._ensure_source_checkbox(path.name)
            if path not in self._session_files:
                self._session_files.append(path)
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            new_events.extend(parse_events(path.name, lines))

        if not new_events:
            return

        combined = deduplicate(self._events + new_events)
        assign_t_ms(combined)
        normalize_cycles(combined)
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
        pre_slot = self._config.get("port_map", {}).get(port)
        worker   = SerialWorker(port, baud, pre_slot)
        worker.event_ready.connect(self._on_serial_event)
        worker.raw_line.connect(self._on_raw_line)
        worker.status_msg.connect(
            lambda msg: self.statusBar().showMessage(msg, 5000))
        self._workers.append(worker)
        worker.start()
        self._session_ports[port] = baud
        self._ensure_source_checkbox(port)   # show source immediately, before events arrive
        slot_hint = f" (slot {pre_slot})" if pre_slot is not None else ""
        self.statusBar().showMessage(
            f"Connected to {port}{slot_hint} at {baud} baud", 4000)

    def _disconnect_all(self):
        for worker in self._workers:
            worker.stop()
            worker.wait(1500)
        self._workers.clear()
        self.statusBar().showMessage("All serial ports disconnected.", 3000)

    def _connect_configured_ports(self):
        """Connect every port listed in port_map of rbconfig.json."""
        port_map = self._config.get("port_map", {})
        if not port_map:
            self.statusBar().showMessage(
                "No port_map entries in rbconfig.json.", 4000)
            return
        for port in port_map:
            self._connect_serial(port)

    def _load_configured_files(self):
        """Load every file listed in log_files of rbconfig.json."""
        log_files = self._config.get("log_files", [])
        if not log_files:
            self.statusBar().showMessage(
                "No log_files entries in rbconfig.json.", 4000)
            return
        base = CONFIG_PATH.parent
        paths = [base / f for f in log_files]
        self._load_paths(paths)

    def _on_raw_line(self, port: str, line: str, n_events: int):
        """Append one raw line to the console using HTML colour."""
        name = Path(port).name

        if n_events:
            color = "#6AFF6A"   # green  — produced an event
        else:
            tick, _ = extract_tick_msg(line)
            color = "#FFD700" if tick is not None else "#888888"
            # yellow = tick present but no event; grey = no tick prefix

        safe = html.escape(f"{name}: {line}")
        self._console.append(f'<span style="color:{color};">{safe}</span>')

        # Keep at most _MAX_CONSOLE_LINES blocks
        doc = self._console.document()
        while doc.blockCount() > _MAX_CONSOLE_LINES:
            cur = self._console.textCursor()
            cur.movePosition(cur.MoveOperation.Start
                             if hasattr(cur.MoveOperation, "Start")
                             else cur.Start)
            cur.select(cur.SelectionType.BlockUnderCursor
                       if hasattr(cur.SelectionType, "BlockUnderCursor")
                       else cur.BlockUnderCursor)
            cur.removeSelectedText()
            cur.deleteChar()
            self._console.setTextCursor(cur)

        if self._auto_scroll:
            sb = self._console.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_serial_event(self, event: dict):
        """Called from SerialWorker thread — only touches _pending (mutex-protected)."""
        with QMutexLocker(self._mutex):
            self._pending.append(event)

    def _flush_pending(self):
        """Called by timer in the main thread every 250 ms."""
        # Always update the rx-label so the user sees live line counts / errors
        if not self._paused:
            parts = []
            for w in self._workers:
                name = Path(w._port).name
                if w.open_error:
                    parts.append(f"⚠ {name}: {w.open_error}")
                elif w.isRunning():
                    src_events = sum(
                        1 for e in self._events
                        if e.get("source_file") == w._port)
                    if w.lines_rx > 0 and src_events == 0:
                        # Lines received but parser hasn't matched anything yet
                        raw = w.last_line[-60:] if len(w.last_line) > 60 else w.last_line
                        parts.append(
                            f"{name}: {w.lines_rx} lines rx — "
                            f"waiting for TXFRAME/RXFRAME … last: {raw!r}")
                    else:
                        parts.append(f"{name}: {w.lines_rx} lines  {src_events} events")
                else:
                    parts.append(f"{name}: closed")
            if parts:
                err = any(w.open_error for w in self._workers)
                waiting = any(
                    w.lines_rx > 0
                    and sum(1 for e in self._events if e.get("source_file") == w._port) == 0
                    for w in self._workers if not w.open_error and w.isRunning()
                )
                self._rx_label.setText("  │  ".join(parts))
                self._rx_label.setStyleSheet(
                    "color: #B03030; font-size: 8pt;" if err else
                    "color: #806000; font-size: 8pt;" if waiting else
                    "color: #444; font-size: 8pt;")
            else:
                self._rx_label.setText("")

        if self._paused:
            return
        with QMutexLocker(self._mutex):
            if not self._pending:
                return
            batch         = self._pending[:]
            self._pending = []

        # Handle device-reset sentinels: clear all stored events for that source
        reset_sources = {
            evt["source_file"]
            for evt in batch
            if evt.get("type") == "_RESET_"
        }
        if reset_sources:
            self._events = [
                e for e in self._events
                if e.get("source_file") not in reset_sources
            ]
            for src in reset_sources:
                self._source_slots.pop(src, None)
            self.statusBar().showMessage(
                "Device reset detected — history cleared for: "
                + ", ".join(sorted(reset_sources)), 4000)
        # Strip sentinels — they must not reach the table
        batch = [e for e in batch if e.get("type") != "_RESET_"]

        # Learn confirmed slots from this batch
        for evt in batch:
            src  = evt.get("source_file")
            slot = evt.get("device_slot")
            if src and slot is not None and slot != -1 and src not in self._source_slots:
                self._source_slots[src] = slot

        # Retroactively fix -1 events in batch and in already-stored events
        for src, slot in self._source_slots.items():
            for evt in batch:
                if evt.get("source_file") == src and evt.get("device_slot") == -1:
                    evt["device_slot"] = slot
            for evt in self._events:
                if evt.get("source_file") == src and evt.get("device_slot") == -1:
                    evt["device_slot"] = slot

        # Remember which (slot, type, tick) keys are already in the table
        old_keys = {
            (e.get("device_slot"), e.get("type"), e.get("tick"))
            for e in self._events
        }

        combined = deduplicate(self._events + batch)
        assign_t_ms(combined)
        normalize_cycles(combined)
        combined.sort(key=lambda e: e.get("t_ms", 0))

        # Truly new events = events not present before this batch
        truly_new = [
            e for e in combined
            if (e.get("device_slot"), e.get("type"), e.get("tick")) not in old_keys
        ]
        if not truly_new:
            return   # all duplicates — nothing to update

        self._events = combined

        # Fast path: all new events sort at the END of the existing table
        # → append rows without clearing the table (avoids blank-flash)
        max_existing_t = max(
            (e.get("t_ms", 0) for e in combined if e not in truly_new),
            default=-1,
        )
        can_append = all(e.get("t_ms", 0) >= max_existing_t for e in truly_new)

        if can_append:
            active_types   = {t for t, cb in self._type_checks.items()  if cb.isChecked()}
            active_devices = {s for s, cb in self._device_checks.items() if cb.isChecked()}
            for event in truly_new:
                slot = event.get("device_slot")
                if slot is not None and slot not in self._device_checks:
                    self._rebuild_table()   # new slot → full rebuild for checkbox
                    return
                src = event.get("source_file", "")
                if src:
                    self._ensure_source_checkbox(src)
                visible = (
                    event["type"] in active_types
                    and event.get("device_slot") in active_devices
                )
                self._insert_row(event, visible)
            self._update_status()
            if self._auto_scroll:
                self._table.scrollToBottom()
        else:
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
        device_names = self._config.get("device_names", {})
        for slot in slots:
            if slot not in self._device_checks:
                colour = slot_color(slot)
                if slot == -1:
                    label = "Slot ? (unbekannt)"
                else:
                    name  = device_names.get(str(slot), "")
                    label = f"Slot {slot}" + (f" — {name}" if name else "")
                # Add to legend
                if slot not in self._legend_slot_widgets:
                    w = self._swatch_row(colour, label)
                    self._legend_slot_widgets[slot] = w
                    self._legend_layout.addWidget(w)
                cb = QCheckBox(label)
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

        # Ensure any sources seen in events have a checkbox (e.g. after reload)
        for src in sorted({e.get("source_file", "") for e in self._events} - {""}):
            self._ensure_source_checkbox(src)

    def _insert_row(self, event: dict, visible: bool = True):
        """Append one row to the table."""
        slot = event.get("device_slot")
        if slot is not None:
            row_brush = QBrush(QColor(slot_color(slot)))
        else:
            row_brush = QBrush(QColor(EVENT_TYPES.get(event["type"], ("", "#FFFFFF"))[1]))
        row_values = event_to_row(event)

        row = self._table.rowCount()
        self._table.insertRow(row)

        source = event.get("source_file", "")
        for col_idx, (col_name, _, _, alignment) in enumerate(COLUMNS):
            item = QTableWidgetItem(row_values[col_idx])
            item.setBackground(row_brush)
            item.setTextAlignment(alignment)
            if col_idx == 0:
                item.setData(_SOURCE_ROLE, source)   # source stored here, not in a column
            self._table.setItem(row, col_idx, item)

        if not visible:
            self._table.setRowHidden(row, True)

    def _apply_filter(self):
        """Show/hide rows without rebuilding the table."""
        active_types   = {t for t, cb in self._type_checks.items()   if cb.isChecked()}
        active_devices = {s for s, cb in self._device_checks.items() if cb.isChecked()}
        active_sources = {s for s, cb in self._source_checks.items() if cb.isChecked()}

        type_col = COL_IDX["type"]
        dev_col  = COL_IDX["slot"]

        for row in range(self._table.rowCount()):
            type_item = self._table.item(row, type_col)
            dev_item  = self._table.item(row, dev_col)
            t_item    = self._table.item(row, 0)
            if type_item is None or dev_item is None:
                continue
            event_type  = type_item.text()
            dev_text    = dev_item.text()
            source_text = (t_item.data(_SOURCE_ROLE) or "") if t_item else ""
            try:
                dev_val = int(dev_text)
                visible = (
                    event_type in active_types
                    and dev_val in active_devices
                    and (not active_sources or source_text in active_sources)
                )
            except ValueError:
                visible = False
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
        ka = by_type.get("KA_TX", 0) + by_type.get("KA_RX", 0)
        self._status_label.setText(
            f"{total} events  "
            f"({by_type['TX']} TX  {by_type['RX']} RX  "
            f"{by_type['ACK_TX']} ACK>  {by_type['ACK_RX']} ACK<"
            + (f"  {ka} KA" if ka else "") +
            f")  │  "
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
        for w in list(self._legend_slot_widgets.values()):
            self._legend_layout.removeWidget(w)
            w.deleteLater()
        self._legend_slot_widgets.clear()
        for w in list(self._source_rows.values()):
            self._source_layout.removeWidget(w)
            w.deleteLater()
        self._source_checks.clear()
        self._source_rows.clear()
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

    def _open_config_dialog(self):
        dlg = ConfigDialog(self)
        dlg.populate_from_config(self._config)
        if not _exec(dlg):
            return
        for port, baud in dlg.port_entries:
            self._connect_serial(port, baud)
        paths = [Path(p) for p in dlg.log_file_paths]
        if paths:
            self._load_paths(paths)
        self._save_config()

    def _save_config(self):
        """Persist current session sources back to rbconfig.json."""
        cfg = dict(self._config)

        # port_map: merge session ports with discovered slots
        port_map = {}
        for port, _baud in self._session_ports.items():
            slot = self._source_slots.get(port)
            port_map[port] = slot
        if port_map:
            cfg["port_map"] = port_map

        # log_files: relative to config dir where possible
        base = CONFIG_PATH.parent
        log_files = []
        for p in self._session_files:
            try:
                log_files.append(str(p.relative_to(base)))
            except ValueError:
                log_files.append(str(p))
        if log_files:
            cfg["log_files"] = log_files

        try:
            CONFIG_PATH.write_text(
                json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"Warning: could not save {CONFIG_PATH}: {exc}", file=sys.stderr)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Save config, then stop all serial threads cleanly before exiting."""
        self._save_config()
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
    else:
        cfg = load_config(CONFIG_PATH)
        if not cfg.get("port_map") and not cfg.get("log_files"):
            # No sources configured at all — ask the user
            dlg = ConfigDialog(window)
            if _exec(dlg):
                for port, baud in dlg.port_entries:
                    window._connect_serial(port, baud)
                paths = [Path(p) for p in dlg.log_file_paths]
                if paths:
                    window._load_paths(paths)
                window._save_config()

    try:
        sys.exit(app.exec())
    except AttributeError:
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()
