"""Offline chip-test record validation and reporting. Never opens hardware."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import sys

UNITS = {
    'A': ('A', 1), 'mA': ('A', 1e-3), 'uA': ('A', 1e-6),
    'µA': ('A', 1e-6), 'μA': ('A', 1e-6), 'nA': ('A', 1e-9),
    'V': ('V', 1), 'mV': ('V', 1e-3),
    'Hz': ('Hz', 1), 'kHz': ('Hz', 1e3), 'MHz': ('Hz', 1e6),
    's': ('s', 1), 'ms': ('s', 1e-3), 'us': ('s', 1e-6),
    'µs': ('s', 1e-6), 'ns': ('s', 1e-9),
    'ohm': ('ohm', 1), 'kohm': ('ohm', 1e3),
    'pF': ('F', 1e-12), 'bit': ('bit', 1), 'dB': ('dB', 1),
}
SOURCES = {'measured_auto', 'measured_manual', 'simulated', 'design', 'calculated'}
CHECKS = {'pass', 'fail', 'not_checked'}
REQUIRED_CONDITIONS = ('supply_v', 'temperature_c', 'power_mode')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def load(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        data = json.load(stream, object_pairs_hook=unique_object)
    return validate(data)


def validate(data):
    need(isinstance(data, dict), 'Top level must be an object')
    # Reject NaN/Infinity even in conditions or additional metadata.
    try:
        json.dumps(data, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError('Data must contain only finite JSON values') from exc
    need(type(data.get('schema_version')) is int and data['schema_version'] == 1,
         'schema_version must be integer 1')
    need(text(data.get('campaign_id')), 'campaign_id is required')
    need(isinstance(data.get('points'), list) and bool(data['points']),
         'points must be a non-empty list')
    ids = set()
    for i, point in enumerate(data['points']):
        tag = 'point[' + str(i) + ']'
        need(isinstance(point, dict), tag + ' must be an object')
        for key in ('id', 'sample_id', 'parameter', 'unit', 'source_ref'):
            need(text(point.get(key)), tag + ': missing ' + key)
        need(point['id'] not in ids, tag + ': duplicate id')
        ids.add(point['id'])
        need(point['unit'] in UNITS, tag + ': unsupported unit')
        need(point.get('source_kind') in SOURCES, tag + ': invalid source_kind')
        for key in ('precheck', 'postcheck'):
            need(point.get(key) in CHECKS, tag + ': invalid ' + key)
        conditions = point.get('conditions')
        need(isinstance(conditions, dict), tag + ': conditions must be an object')
        for key in ('supply_v', 'temperature_c', 'sysclk_hz', 'hclk_hz'):
            value = conditions.get(key)
            if value is not None:
                need(number(value), tag + ': ' + key + ' must be numeric or null')
                if key != 'temperature_c':
                    need(value > 0, tag + ': ' + key + ' must be positive')
        if conditions.get('power_mode') is not None:
            need(text(conditions['power_mode']), tag + ': power_mode must be text or null')
        for key in ('expected_registers', 'observed_registers'):
            regs = point.get(key, {})
            need(isinstance(regs, dict), tag + ': ' + key + ' must be an object')
            need(all(text(k) and (isinstance(v, str) or type(v) is int)
                     for k, v in regs.items()), tag + ': register values must be strings or integers')
        minimum = point.get('min_valid_samples')
        need(type(minimum) is int and minimum >= 1, tag + ': min_valid_samples must be a positive integer')
        observations = point.get('observations')
        need(isinstance(observations, list), tag + ': observations must be a list')
        for j, obs in enumerate(observations):
            label = tag + '/observation[' + str(j) + ']'
            need(isinstance(obs, dict), label + ' must be an object')
            need(obs.get('status') in ('valid', 'invalid'), label + ': invalid status')
            need(text(obs.get('timestamp')), label + ': timestamp is required')
            try:
                stamp = datetime.fromisoformat(obs['timestamp'].replace('Z', '+00:00'))
            except ValueError as exc:
                raise ValueError(label + ': invalid ISO timestamp') from exc
            need(stamp.utcoffset() is not None, label + ': timestamp needs a timezone')
            if obs['status'] == 'valid':
                need(number(obs.get('value')), label + ': valid reading must be finite numeric')
            else:
                need(text(obs.get('reason')), label + ': invalid reading needs a reason')
                need(obs.get('value') is None or number(obs['value']), label + ': invalid value')
    return data


def summarize(point):
    values = [o['value'] for o in point['observations'] if o['status'] == 'valid']
    conditions = point['conditions']
    missing = [k for k in REQUIRED_CONDITIONS if conditions.get(k) is None]
    expected = point.get('expected_registers', {})
    observed = point.get('observed_registers', {})
    mismatch = [k for k, v in expected.items() if k not in observed or observed[k] != v]
    issues = []
    if mismatch:
        issues.append('register mismatch/missing: ' + ', '.join(mismatch))
    if missing:
        issues.append('missing conditions: ' + ', '.join(missing))
    for check in ('precheck', 'postcheck'):
        if point[check] != 'pass':
            issues.append(check + '=' + point[check])
    if len(values) < point['min_valid_samples']:
        issues.append('insufficient valid observations')
    invalid = len(point['observations']) - len(values)
    if invalid:
        issues.append(str(invalid) + ' invalid observation(s) excluded; originals retained')
    blocked = bool(mismatch) or 'fail' in (point['precheck'], point['postcheck'])
    incomplete = bool(missing) or 'not_checked' in (point['precheck'], point['postcheck']) or len(values) < point['min_valid_samples']
    state = 'blocked' if blocked else 'incomplete' if incomplete else (
        'simulated' if point['source_kind'] == 'simulated' else
        'reference' if point['source_kind'] in ('design', 'calculated') else 'review')
    mean = statistics.mean(values) if values else None
    si_unit, factor = UNITS[point['unit']]
    return dict(id=point['id'], sample_id=point['sample_id'], parameter=point['parameter'],
                source_kind=point['source_kind'], source_ref=point['source_ref'],
                review_state=state, valid_count=len(values), invalid_count=invalid,
                observed_min=min(values) if values else None, observed_mean=mean,
                observed_max=max(values) if values else None,
                sample_stddev=statistics.stdev(values) if len(values) > 1 else None,
                unit=point['unit'], mean_si=mean * factor if mean is not None else None,
                si_unit=si_unit, conditions=json.dumps(conditions, ensure_ascii=False, sort_keys=True),
                issues='; '.join(issues))


def csv_cell(value):
    # Numeric results remain numeric; protect user-provided text in spreadsheet viewers.
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def md(value):
    if value is None:
        return ''
    return (str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('\\', '\\\\').replace('|', '\\|').replace('\r', ' ').replace('\n', ' '))


def report(data, out_dir):
    validate(data)
    rows = [summarize(p) for p in data['points']]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'validated_input.json').write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                                       allow_nan=False) + '\n', encoding='utf-8')
    with (out / 'summary.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: csv_cell(v) for k, v in row.items()})
    lines = ['# Chip test report', '', 'Campaign: ' + md(data['campaign_id']), '',
             '**Observed statistics only. No guaranteed DS limits are inferred.**', '',
             'Simulated / design / calculated records are explicitly distinguished. '
             'Review means ready for human review, not a passing device.', '',
             '| Point | Sample | Parameter | Source | State | N | Min observed | Mean observed | Max observed | Unit |',
             '|---|---|---|---|---|---:|---:|---:|---:|---|']
    keys = ('id', 'sample_id', 'parameter', 'source_kind', 'review_state', 'valid_count',
            'observed_min', 'observed_mean', 'observed_max', 'unit')
    for row in rows:
        lines.append('| ' + ' | '.join(md(row[k]) for k in keys) + ' |')
    for row in rows:
        lines += ['', '## ' + md(row['id']), '', 'Source: ' + md(row['source_ref']), '',
                  'Conditions: ' + md(row['conditions']), '',
                  'Issues: ' + md(row['issues'] or 'none detected by offline checks')]
    (out / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('validate', help='Validate schema; does not certify measurements').add_argument('input')
    p = subs.add_parser('report', help='Write per-point CSV/Markdown and preserve input')
    p.add_argument('input')
    p.add_argument('--out-dir', required=True, help='New output directory; never overwrite')
    args = parser.parse_args(argv)
    try:
        data = load(args.input)
        rows = report(data, args.out_dir) if args.command == 'report' else [summarize(p) for p in data['points']]
        print(json.dumps({'schema_valid': True, 'points': len(rows),
                          'states': {r['id']: r['review_state'] for r in rows}}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
