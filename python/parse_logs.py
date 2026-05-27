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


def parse_frames(source_file, lines):
    device_slot = parse_device_slot(lines)
    anchors = parse_anchors(lines)
    frames = []
    i = 0

    while i < len(lines):
        tick, msg = extract_tick_msg(lines[i])
        if msg is None:
            i += 1
            continue

        m = re.match(r'(TXFRAME|RXFRAME)\s*\(c:\s*(\d+),\s*(\d+),\s*(\d+)\)', msg)
        if not m:
            i += 1
            continue

        frame = {
            'source_file': source_file,
            'device_slot': device_slot,
            'type': 'TX' if m.group(1) == 'TXFRAME' else 'RX',
            'tick': tick,
            '_epoch_ms': tick_to_epoch_ms(tick, anchors) if anchors else None,
            'af_slot': None,
            'pl_slot': None,
            'hubCnt': None,
            'state': {},
            'dirty': False,
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
                frame['af_slot'] = int(m_af.group(1))
                j += 1
                continue

            m_pl = re.match(r'PL\s+slot\s*=\s*(\d+)', msg2)
            if m_pl:
                frame['pl_slot'] = int(m_pl.group(1))
                j += 1
                continue

            m_hub = re.match(r'hubCnt\s*=\s*(\d+)', msg2)
            if m_hub:
                frame['hubCnt'] = int(m_hub.group(1))
                j += 1
                continue

            if msg2 == 'state':
                j += 1
                continue

            m_label = re.match(r'label\s*=\s*(.*)', msg2)
            if m_label:
                labels = m_label.group(1).split()
                j += 1
                continue

            m_state = re.match(r'State\s*=\s*(.*)', msg2)
            if m_state and labels is not None:
                values = m_state.group(1).split()
                frame['state'] = {
                    labels[k].lower(): values[k]
                    for k in range(min(len(labels), len(values)))
                }
                j += 1
                continue

            if msg2 == 'Dirty':
                frame['dirty'] = True
                j += 1
                break

            break

        frames.append(frame)
        i = j

    return frames


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


def deduplicate(all_frames):
    """Remove frames with identical (device_slot, tick) — same physical event."""
    seen: set = set()
    result = []
    for f in all_frames:
        key = (f['device_slot'], f['tick'])
        if key not in seen:
            seen.add(key)
            result.append(f)
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
        state_items = ', '.join(f"'{k}': '{v}'" for k, v in f['state'].items())
        lines += [
            '    {',
            f"        't_ms': {f['t_ms']:010d},",
            f"        'source_file': '{f['source_file']}',",
            f"        'device_slot': {f['device_slot']},",
            f"        'type': '{f['type']}',",
            f"        'tick': {f['tick']},",
            f"        'af_slot': {f['af_slot']},",
            f"        'pl_slot': {f['pl_slot']},",
            f"        'hubCnt': {f['hubCnt']},",
            f"        'state': {{{state_items}}},",
            f"        'dirty': {f['dirty']},",
            '    },',
        ]

    lines += [']', '']
    return '\n'.join(lines)


def print_timeline(all_frames):
    header = (
        f"{'t_ms':>10}  {'dev':>3}  {'typ':>2}  "
        f"{'af':>2}  {'pl':>2}  {'hub':>3}  {'dirty':>5}  active states"
    )
    print()
    print(header)
    print('-' * len(header))
    for f in all_frames:
        active = ' '.join(f"{k}={v}" for k, v in f['state'].items() if v != 'OFF') or '-'
        print(
            f"{f['t_ms']:010d}  {f['device_slot']:>3}  {f['type']:>2}  "
            f"{f['af_slot']:>2}  {f['pl_slot']:>2}  {f['hubCnt']:>3}  "
            f"{'Y' if f['dirty'] else 'N':>5}  {active}"
        )
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
        frames = parse_frames(log_file.name, raw)
        slot = frames[0]['device_slot'] if frames else '?'
        print(f"{log_file.name}: {len(frames)} frames  (device slot {slot})")
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
        slots.setdefault(k, {'TX': 0, 'RX': 0})
        slots[k][f['type']] += 1
    print("\nPer device:")
    for s in sorted(slots):
        print(f"  slot {s}: {slots[s]['TX']} TX, {slots[s]['RX']} RX")


if __name__ == '__main__':
    main()
