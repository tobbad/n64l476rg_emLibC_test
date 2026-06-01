#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RadioBell log parsing — the single source of truth for turning device output
into structured events, shared by both the file and the live-serial path.

The core is the StreamParser class: a stateful, line-by-line parser that turns
RadioBell log lines into event dicts (TX/RX/ACK/KA/DATA, plus AppliFrame/
Payload/State fields).  It is used in two ways:

  * Files  – parse_events() feeds a whole captured python/log/*.txt through a
             StreamParser at once (batch).  Anchors come from the embedded
             "[RX] - <tick>:" PC timestamps in the file.
  * Serial – viewer.py's SerialWorker feeds the same StreamParser one line at a
             time as they arrive from the port, seeding the first tick→time
             anchor itself (live serial output has no embedded timestamps).

Both paths produce identical event dicts; only anchor seeding and device-reset
detection differ, controlled by StreamParser's constructor arguments.

Run as a script (`python parse_logs.py`), this module parses all files in
python/log/*.txt and generates python/simulation/simulation_data.py.  A unified
tick t_ms (ms since the first event across all devices) is derived from the
anchors; device ticks run at ~1 ms/tick.  Duplicate events (same device, type
and tick) are removed.
"""
import re
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / "log"
OUTPUT_FILE = Path(__file__).parent / "simulation" / "simulation_data.py"

_ANCHOR_RE = re.compile(
    r'(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+\[RX\]\s+-\s+(\d{10}):'
)


def extract_tick_msg(line):
    m = re.search(r'(\d{10}):\s*(.*)', line)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, None


def tick_to_epoch_ms(tick, anchors):
    """Convert device tick to epoch ms using the closest prior anchor."""
    best = None
    for epoch_ms, anchor_tick in anchors:
        if anchor_tick <= tick:
            if best is None or anchor_tick > best[1]:
                best = (epoch_ms, anchor_tick)
    if best is None:
        best = min(anchors, key=lambda a: a[1])
    return best[0] + (tick - best[1])


class StreamParser:
    """
    Single, stateful parser for RadioBell log lines — used both for whole
    files (via parse_events) and for live serial streams (SerialWorker).

    Call feed(line) for every incoming line; it returns a list of complete
    events (usually 0 or 1).  Multi-line TXFRAME/RXFRAME blocks are buffered
    internally and emitted only when complete, so a single source of truth
    handles both batch and streaming use.  Call flush() once at the end of a
    file to release a still-pending frame.

    Event types produced:
      - 'TX'/'RX'   : TXFRAME: / RXFRAME: data frame blocks
      - 'ACK_TX'    : rb_system.txFrame->Cmd = ACK_OK
      - 'ACK_RX'    : SM_STATE_ACK_RECEIVED from slot X
      - 'KA_TX'     : Send SM_STATE_KEEP_ALIVE
      - 'KA_RX'     : SM_STATE_KEEP_ALIVE
      - 'DATA_RX'   : SM_STATE_DATA_RECEIVED N Bytes
      - '_RESET_'   : device restarted (only when detect_reset=True)

    Anchors (device tick → PC epoch ms) are learned from the embedded
    "[RX] - <tick>:" timestamp lines present in files.  For a live serial
    stream those lines do not exist, so SerialWorker seeds self.anchors
    with a single (now, first_tick) pair instead.
    """

    def __init__(self, source_name, device_slot=None, detect_reset=True):
        self.source_name  = source_name
        self.device_slot  = device_slot   # pre-set from config; overwritten by "my_slot = X"
        self.detect_reset = detect_reset
        self.anchors      = []            # (epoch_ms, device_tick) anchor pairs
        self._frame       = None          # pending multi-line frame being built
        self._labels      = None          # label row from the pending frame
        self._slot_seen   = False         # True after first my_slot line; second = reset

    # ── internal helpers ──────────────────────────────────────────────────────

    def _epoch_ms(self, tick):
        return tick_to_epoch_ms(tick, self.anchors) if self.anchors else None

    def _base_event(self, tick, event_type):
        return {
            'source_file': self.source_name,
            'device_slot': self.device_slot if self.device_slot is not None else -1,
            'type':        event_type,
            'tick':        tick,
            '_epoch_ms':   self._epoch_ms(tick),
        }

    def _flush_frame(self):
        """Return and clear the pending frame."""
        frame, self._frame, self._labels = self._frame, None, None
        return frame

    def flush(self):
        """Release a still-pending frame at end of input. Returns 0 or 1 events."""
        return [self._flush_frame()] if self._frame else []

    # ── public interface ──────────────────────────────────────────────────────

    def feed(self, line):
        """Feed one log line. Returns a list of complete events (usually 0 or 1)."""
        # ── Learn an anchor from the embedded PC timestamp (files only) ────
        a = _ANCHOR_RE.search(line)
        if a:
            dt = datetime.strptime(a.group(1), '%d.%m.%Y %H:%M:%S.%f')
            self.anchors.append((int(dt.timestamp() * 1000), int(a.group(2))))

        tick, msg = extract_tick_msg(line)
        if msg is None:
            return []

        emitted = []

        # ── Learn the device slot from the EEPROM header (authoritative) ───
        m = re.match(r'my_slot\s*=\s*(\d+)', msg)
        if m:
            new_slot = int(m.group(1))
            if self.detect_reset and self._slot_seen:
                # Second occurrence → device has been reset; signal the caller
                self.anchors.clear()   # SerialWorker will set a fresh anchor
                emitted.append({
                    'type':        '_RESET_',
                    'source_file': self.source_name,
                    'device_slot': new_slot,
                    '_epoch_ms':   None,
                })
            self.device_slot = new_slot
            self._slot_seen  = True

        # ── New data frame starting ───────────────────────────────────────
        m = re.match(r'(TXFRAME|RXFRAME):?\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)', msg)
        if m:
            if self._frame:                       # flush any unfinished frame
                emitted.append(self._flush_frame())
            frame = self._base_event(tick, 'TX' if m.group(1) == 'TXFRAME' else 'RX')
            frame.update({
                'cycle':   int(m.group(2)),
                'af_slot': int(m.group(3)),   # sender slot (af_slot = slot in c:)
                'subslot': int(m.group(4)),   # subslot within slot
                'pl_slot': None,
                'hubCnt':  None,
                'state':   {},
                'dirty':   False,
            })
            self._frame = frame
            return emitted

        # ── Continue building the pending frame ───────────────────────────
        if self._frame is not None:
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
            if (m := re.match(r'State\s*=\s*(.*)', msg)) and self._labels is not None:
                values = m.group(1).split()
                pf['state'] = {
                    self._labels[k].lower(): values[k]
                    for k in range(min(len(self._labels), len(values)))
                }
                return emitted
            if msg == 'Dirty':
                pf['dirty'] = True
                emitted.append(self._flush_frame())
                return emitted
            # Any unrelated line means the frame block is done
            emitted.append(self._flush_frame())

        # ── ACK sent: rb_system.txFrame->Cmd = ACK_OK (c: cycle, slot, subslot) ─
        m = re.match(
            r'rb_system\.txFrame->Cmd\s*=\s*ACK_OK\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)', msg)
        if m:
            evt = self._base_event(tick, 'ACK_TX')
            evt.update({
                'cycle':   int(m.group(1)),
                'af_slot': int(m.group(2)),   # sender slot (= this device's slot)
                'subslot': int(m.group(3)),
            })
            emitted.append(evt)
            return emitted

        # ── ACK received: SM_STATE_ACK_RECEIVED from slot X (c: cycle, slot, subslot) ─
        m = re.match(
            r'SM_STATE_ACK_RECEIVED\s+from\s+slot\s+(\d+)\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)', msg)
        if m:
            evt = self._base_event(tick, 'ACK_RX')
            evt.update({
                'from_slot': int(m.group(1)),
                'af_slot':   int(m.group(1)),   # ACK sender = from_slot
                'cycle':     int(m.group(2)),
                'subslot':   int(m.group(4)),
            })
            emitted.append(evt)
            return emitted

        # ── KEEP_ALIVE sent: Send SM_STATE_KEEP_ALIVE (c: cycle, slot, subslot) ─
        m = re.match(
            r'Send\s+SM_STATE_KEEP_ALIVE\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)', msg)
        if m:
            evt = self._base_event(tick, 'KA_TX')
            evt.update({
                'cycle':   int(m.group(1)),
                'af_slot': int(m.group(2)),
                'subslot': int(m.group(3)),
            })
            emitted.append(evt)
            return emitted

        # ── KEEP_ALIVE received: SM_STATE_KEEP_ALIVE (c: cycle, slot, subslot) ─
        m = re.match(
            r'SM_STATE_KEEP_ALIVE\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)', msg)
        if m:
            evt = self._base_event(tick, 'KA_RX')
            evt.update({
                'cycle':   int(m.group(1)),
                'af_slot': int(m.group(2)),
                'subslot': int(m.group(3)),
            })
            emitted.append(evt)
            return emitted

        # ── Radio bytes received: SM_STATE_DATA_RECEIVED N Bytes (from slot = X) ─
        m = re.match(
            r'SM_STATE_DATA_RECEIVED\s+(\d+)\s+Bytes\s+\(from\s+slot\s*=\s*(\d+)\)', msg)
        if m:
            evt = self._base_event(tick, 'DATA_RX')
            evt.update({
                'af_slot': int(m.group(2)),
                'info':    f"{m.group(1)} B from slot {m.group(2)}",
            })
            emitted.append(evt)
            return emitted

        return emitted


def parse_events(source_file, lines):
    """
    Parse a complete list of log lines into events, using StreamParser.

    This is the batch entry point (file input); the live serial path uses the
    same StreamParser one line at a time.  reset detection is disabled here —
    a re-flashed device mid-file just continues with the new slot.
    """
    parser = StreamParser(source_file, detect_reset=False)
    events = []
    for line in lines:
        events.extend(parser.feed(line))
    events.extend(parser.flush())
    return [e for e in events if e.get('type') != '_RESET_']


def assign_t_ms(all_frames):
    """
    Set t_ms on every frame: ms since the earliest event across all devices.
    Same zero-padded style as device ticks.

    This is what puts file and serial events onto ONE shared timeline: every
    event already carries an absolute PC-epoch ms (_epoch_ms, derived from its
    source's anchors), so subtracting the global minimum yields a common t_ms
    regardless of source.  Mixing sources captured far apart in wall-clock time
    (e.g. an old log file plus a live serial session) therefore produces a
    correspondingly large t_ms gap between them.  Callers re-run this whenever a
    source is added so the zero point stays at the earliest event seen.
    """
    valid = [f for f in all_frames if f['_epoch_ms'] is not None]
    if not valid:
        for f in all_frames:
            f['t_ms'] = 0
        return
    origin = min(f['_epoch_ms'] for f in valid)
    for f in all_frames:
        f['t_ms'] = (f['_epoch_ms'] - origin) if f['_epoch_ms'] is not None else 0


def deduplicate(all_events):
    """Remove events with identical (device_slot, type, tick) — same physical event."""
    seen: set = set()
    result = []
    for e in all_events:
        key = (e['device_slot'], e['type'], e['tick'])
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result


def generate_output(all_frames):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = [
        '#!/usr/bin/env python3',
        '# -*- coding: utf-8 -*-',
        f'# Auto-generated by parse_logs.py on {now}',
        '# Source: python/log/*.txt',
        '#',
        '# Sorted by t_ms (unified ms counter, 0 = first event across all devices).',
        '# Fields:',
        '#   t_ms         – unified tick: ms since first event (same style as device ticks)',
        '#   source_file  – which log file this came from',
        '#   device_slot  – slot number of the device that produced this log',
        "#   type         – 'TX' (sent by device) or 'RX' (received by device)",
        '#   tick         – original device tick counter',
        '#   af_slot      – AppliFrame slot field',
        '#   pl_slot      – Payload slot field',
        '#   hubCnt       – hub counter',
        "#   state        – dict hex-label -> 'OFF'/'BLI'/'ON' for all 16 keys",
        '#   dirty        – True if the Dirty flag was set',
        '',
        'frames = [',
    ]

    for f in all_frames:
        row = [
            '    {',
            f"        't_ms': {f['t_ms']:010d},",
            f"        'source_file': '{f['source_file']}',",
            f"        'device_slot': {f['device_slot']},",
            f"        'type': '{f['type']}',",
            f"        'tick': {f['tick']},",
        ]
        if f['type'] in ('TX', 'RX'):
            state_items = ', '.join(f"'{k}': '{v}'" for k, v in f['state'].items())
            row += [
                f"        'af_slot': {f['af_slot']},",
                f"        'pl_slot': {f['pl_slot']},",
                f"        'hubCnt': {f['hubCnt']},",
                f"        'state': {{{state_items}}},",
                f"        'dirty': {f['dirty']},",
            ]
        elif f['type'] == 'ACK_RX':
            row.append(f"        'from_slot': {f['from_slot']},")
        row.append('    },')
        lines += row

    lines += [']', '']
    return '\n'.join(lines)


def print_timeline(all_events):
    header = (
        f"{'t_ms':>10}  {'dev':>3}  {'type':<6}  info"
    )
    print()
    print(header)
    print('-' * 60)
    for e in all_events:
        t = f"{e['t_ms']:010d}"
        dev = f"{e['device_slot']:>3}"
        typ = e['type']

        if typ in ('TX', 'RX'):
            active = ' '.join(
                f"{k}={v}" for k, v in e['state'].items() if v != 'OFF'
            ) or '-'
            dirty = 'D' if e['dirty'] else ' '
            info = (
                f"af={e['af_slot']:>2}  pl={e['pl_slot']:>2}  "
                f"hub={e['hubCnt']:>2}  {dirty}  {active}"
            )
        elif typ == 'ACK_TX':
            info = '>> ACK sent'
        elif typ == 'ACK_RX':
            info = f"<< ACK from slot {e['from_slot']}"
        elif typ == 'KA_TX':
            info = '>> KA sent'
        elif typ == 'KA_RX':
            info = '<< KA received'
        else:  # DATA_RX
            info = e.get('info', 'radio bytes received')

        print(f"{t}  {dev}  {typ:<6}  {info}")
    print()


def main():
    log_files = sorted(LOG_DIR.glob('*.txt'))
    if not log_files:
        print(f"No .txt files found in {LOG_DIR}")
        return

    all_frames = []
    for log_file in log_files:
        with open(log_file, encoding='utf-8', errors='replace') as fh:
            raw = fh.readlines()
        frames = parse_events(log_file.name, raw)
        slot = frames[0]['device_slot'] if frames else '?'
        n_data = sum(1 for f in frames if f['type'] in ('TX', 'RX'))
        n_ack  = sum(1 for f in frames if f['type'] in ('ACK_TX', 'ACK_RX'))
        print(f"{log_file.name}: {n_data} frames, {n_ack} ACKs  (device slot {slot})")
        all_frames.extend(frames)

    all_frames = deduplicate(all_frames)
    assign_t_ms(all_frames)
    all_frames.sort(key=lambda f: f['t_ms'])

    print_timeline(all_frames)

    content = generate_output(all_frames)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content, encoding='utf-8')
    print(f"Wrote {len(all_frames)} frames to {OUTPUT_FILE}")

    slots: dict = {}
    for f in all_frames:
        k = f['device_slot']
        counts = slots.setdefault(k, {})
        counts[f['type']] = counts.get(f['type'], 0) + 1
    print("\nPer device:")
    for s in sorted(slots):
        d = slots[s]
        ka = d.get('KA_TX', 0) + d.get('KA_RX', 0)
        print(f"  slot {s}: {d.get('TX', 0)} TX  {d.get('RX', 0)} RX  "
              f"{d.get('ACK_TX', 0)} ACK>  {d.get('ACK_RX', 0)} ACK<"
              + (f"  {ka} KA" if ka else "")
              + (f"  {d['DATA_RX']} DATA" if d.get('DATA_RX') else ""))


if __name__ == '__main__':
    main()
