#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse device log files from python/log/*.txt and generate
python/simulation/simulation_data.py containing all TXFRAME/RXFRAME events
as a list of dicts with AppliFrame/Payload/State fields.

A unified tick t_ms (ms since first event across all devices) is derived from
the [TX]...[RX] anchor lines embedded in each log file.  Device ticks run at
~1 ms/tick.  Duplicate frames (same device, same tick) are removed.
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


def parse_anchors(lines):
    """Return list of (epoch_ms, device_tick) from [RX] anchor lines."""
    anchors = []
    for line in lines:
        m = _ANCHOR_RE.search(line)
        if m:
            dt = datetime.strptime(m.group(1), '%d.%m.%Y %H:%M:%S.%f')
            anchors.append((int(dt.timestamp() * 1000), int(m.group(2))))
    return anchors


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


def parse_device_slot(lines):
    for line in lines:
        _, msg = extract_tick_msg(line)
        if msg and re.match(r'my_slot\s*=\s*(\d+)', msg):
            return int(re.match(r'my_slot\s*=\s*(\d+)', msg).group(1))
    return None


def parse_events(source_file, lines):
    """
    Extract all events from a log file:
      - type='TX'/'RX'   : TXFRAME: / RXFRAME: data frame blocks
      - type='ACK_TX'    : rb_system.txFrame->Cmd = ACK_OK
      - type='ACK_RX'    : SM_STATE_ACK_RECEIVED from slot X
      - type='KA_TX'     : Send SM_STATE_KEEP_ALIVE
      - type='KA_RX'     : SM_STATE_KEEP_ALIVE
      - type='DATA_RX'   : SM_STATE_DATA_RECEIVED N Bytes
    """
    device_slot = parse_device_slot(lines)
    anchors = parse_anchors(lines)
    events = []
    i = 0

    while i < len(lines):
        tick, msg = extract_tick_msg(lines[i])
        if msg is None:
            i += 1
            continue

        # ── DATA frames ──────────────────────────────────────────────────────
        m = re.match(r'(TXFRAME|RXFRAME):?\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)', msg)
        if m:
            frame = {
                'source_file': source_file,
                'device_slot': device_slot,
                'type': 'TX' if m.group(1) == 'TXFRAME' else 'RX',
                'tick': tick,
                '_epoch_ms': tick_to_epoch_ms(tick, anchors) if anchors else None,
                'cycle':   int(m.group(2)),
                'af_slot': int(m.group(3)),   # sender slot (af_slot = slot in c:)
                'subslot': int(m.group(4)),   # subslot within slot
                'pl_slot': None,
                'hubCnt':  None,
                'state':   {},
                'dirty':   False,
            }
            labels = None
            j = i + 1
            max_j = min(i + 15, len(lines))
            while j < max_j:
                _, msg2 = extract_tick_msg(lines[j])
                if msg2 is None:
                    j += 1
                    continue
                m_af = re.match(r'AF\s+slot\s*=\s*(\d+)', msg2)
                if m_af:
                    frame['af_slot'] = int(m_af.group(1)); j += 1; continue
                m_pl = re.match(r'PL\s+slot\s*=\s*(\d+)', msg2)
                if m_pl:
                    frame['pl_slot'] = int(m_pl.group(1)); j += 1; continue
                m_hub = re.match(r'hubCnt\s*=\s*(\d+)', msg2)
                if m_hub:
                    frame['hubCnt'] = int(m_hub.group(1)); j += 1; continue
                if msg2 == 'state':
                    j += 1; continue
                m_label = re.match(r'label\s*=\s*(.*)', msg2)
                if m_label:
                    labels = m_label.group(1).split(); j += 1; continue
                m_state = re.match(r'State\s*=\s*(.*)', msg2)
                if m_state and labels is not None:
                    values = m_state.group(1).split()
                    frame['state'] = {
                        labels[k].lower(): values[k]
                        for k in range(min(len(labels), len(values)))
                    }
                    j += 1; continue
                if msg2 == 'Dirty':
                    frame['dirty'] = True; j += 1; break
                break
            events.append(frame)
            i = j
            continue

        # ── ACK sent: rb_system.txFrame->Cmd = ACK_OK (c: cycle, slot, subslot) ─
        m_ok = re.match(
            r'rb_system\.txFrame->Cmd\s*=\s*ACK_OK\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)', msg)
        if m_ok:
            events.append({
                'source_file': source_file,
                'device_slot': device_slot,
                'type':    'ACK_TX',
                'tick':    tick,
                '_epoch_ms': tick_to_epoch_ms(tick, anchors) if anchors else None,
                'cycle':   int(m_ok.group(1)),
                'af_slot': int(m_ok.group(2)),   # sender slot (= this device's slot)
                'subslot': int(m_ok.group(3)),
            })
            i += 1
            continue

        # ── ACK received: SM_STATE_ACK_RECEIVED from slot X (c: cycle, slot, subslot) ─
        m_ack = re.match(
            r'SM_STATE_ACK_RECEIVED\s+from\s+slot\s+(\d+)\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)', msg)
        if m_ack:
            events.append({
                'source_file': source_file,
                'device_slot': device_slot,
                'type':      'ACK_RX',
                'tick':      tick,
                '_epoch_ms': tick_to_epoch_ms(tick, anchors) if anchors else None,
                'from_slot': int(m_ack.group(1)),
                'af_slot':   int(m_ack.group(1)),   # ACK sender = from_slot
                'cycle':     int(m_ack.group(2)),
                'subslot':   int(m_ack.group(4)),
            })
            i += 1
            continue

        # ── KEEP_ALIVE sent: Send SM_STATE_KEEP_ALIVE (c: cycle, slot, subslot) ─
        m_ka_tx = re.match(
            r'Send\s+SM_STATE_KEEP_ALIVE\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)', msg)
        if m_ka_tx:
            events.append({
                'source_file': source_file,
                'device_slot': device_slot,
                'type':      'KA_TX',
                'tick':      tick,
                '_epoch_ms': tick_to_epoch_ms(tick, anchors) if anchors else None,
                'cycle':     int(m_ka_tx.group(1)),
                'af_slot':   int(m_ka_tx.group(2)),
                'subslot':   int(m_ka_tx.group(3)),
            })
            i += 1
            continue

        # ── KEEP_ALIVE received: SM_STATE_KEEP_ALIVE (c: cycle, slot, subslot) ─
        m_ka_rx = re.match(
            r'SM_STATE_KEEP_ALIVE\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)', msg)
        if m_ka_rx:
            events.append({
                'source_file': source_file,
                'device_slot': device_slot,
                'type':      'KA_RX',
                'tick':      tick,
                '_epoch_ms': tick_to_epoch_ms(tick, anchors) if anchors else None,
                'cycle':     int(m_ka_rx.group(1)),
                'af_slot':   int(m_ka_rx.group(2)),
                'subslot':   int(m_ka_rx.group(3)),
            })
            i += 1
            continue

        # ── Radio bytes received: SM_STATE_DATA_RECEIVED N Bytes (from slot = X) ─
        m_dr = re.match(
            r'SM_STATE_DATA_RECEIVED\s+(\d+)\s+Bytes\s+\(from\s+slot\s*=\s*(\d+)\)', msg)
        if m_dr:
            events.append({
                'source_file': source_file,
                'device_slot': device_slot,
                'type':      'DATA_RX',
                'tick':      tick,
                '_epoch_ms': tick_to_epoch_ms(tick, anchors) if anchors else None,
                'af_slot':   int(m_dr.group(2)),
                'info':      f"{m_dr.group(1)} B from slot {m_dr.group(2)}",
            })
            i += 1
            continue

        i += 1

    return events


def assign_t_ms(all_frames):
    """
    Set t_ms on every frame: ms since the earliest event across all devices.
    Same zero-padded style as device ticks.
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
        else:  # ACK_RX
            info = f"<< ACK from slot {e['from_slot']}"

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
        slots.setdefault(k, {'TX': 0, 'RX': 0, 'ACK_TX': 0, 'ACK_RX': 0})
        slots[k][f['type']] += 1
    print("\nPer device:")
    for s in sorted(slots):
        d = slots[s]
        print(f"  slot {s}: {d['TX']} TX  {d['RX']} RX  {d['ACK_TX']} ACK>  {d['ACK_RX']} ACK<")


if __name__ == '__main__':
    main()
