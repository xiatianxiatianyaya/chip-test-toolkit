import copy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('results', ROOT / 'chip-test/scripts/results.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.data = r.load(ROOT / 'chip-test/assets/demo.json')

    def test_statistics_and_units_exclude_invalid(self):
        row = r.summarize(self.data['points'][0])
        self.assertEqual((row['valid_count'], row['invalid_count']), (3, 1))
        self.assertEqual(row['observed_mean'], 101)
        self.assertEqual(row['sample_stddev'], 1)
        self.assertAlmostEqual(row['mean_si'], 101e-6)
        self.assertEqual(row['review_state'], 'simulated')

    def test_register_readback_failure_is_blocked(self):
        p = self.data['points'][1]
        p['postcheck'] = 'pass'
        self.assertEqual(r.summarize(p)['review_state'], 'blocked')
        p['observed_registers'] = {}
        self.assertEqual(r.summarize(p)['review_state'], 'blocked')

    def test_missing_conditions_or_check_not_certified(self):
        p = self.data['points'][0]
        p['source_kind'] = 'measured_auto'
        p['conditions']['supply_v'] = None
        self.assertEqual(r.summarize(p)['review_state'], 'incomplete')
        p['conditions']['supply_v'] = 3.3
        p['postcheck'] = 'not_checked'
        self.assertEqual(r.summarize(p)['review_state'], 'incomplete')

    def test_single_manual_reading_has_no_stddev(self):
        p = self.data['points'][0]
        p.update(source_kind='measured_manual', min_valid_samples=1)
        p['observations'] = p['observations'][:1]
        row = r.summarize(p)
        self.assertIsNone(row['sample_stddev'])
        self.assertEqual(row['review_state'], 'review')

    def test_no_valid_samples_preserves_empty_statistics(self):
        p = self.data['points'][0]
        p['observations'] = p['observations'][-1:]
        row = r.summarize(p)
        self.assertIsNone(row['observed_mean'])
        self.assertEqual(row['review_state'], 'incomplete')

    def test_nan_bool_bad_unit_and_duplicate_ids_rejected(self):
        for invalid in (float('nan'), float('inf'), True, '100'):
            data = copy.deepcopy(self.data)
            data['points'][0]['observations'][0]['value'] = invalid
            with self.assertRaises(ValueError): r.validate(data)
        self.data['points'][0]['unit'] = 'unknown'
        with self.assertRaises(ValueError): r.validate(self.data)
        self.data['points'][0]['unit'] = 'uA'
        self.data['points'][1]['id'] = self.data['points'][0]['id']
        with self.assertRaises(ValueError): r.validate(self.data)

    def test_timestamp_timezone_and_invalid_reason_required(self):
        p = self.data['points'][0]
        p['observations'][0]['timestamp'] = '2026-01-01T12:00:00'
        with self.assertRaises(ValueError): r.validate(self.data)
        p['observations'][0]['timestamp'] += '+00:00'
        del p['observations'][-1]['reason']
        with self.assertRaises(ValueError): r.validate(self.data)

    def test_insufficient_samples_and_reference_types(self):
        p = self.data['points'][0]
        p['min_valid_samples'] = 20
        self.assertEqual(r.summarize(p)['review_state'], 'incomplete')
        p['min_valid_samples'] = 3
        for source in ('design', 'calculated'):
            p['source_kind'] = source
            self.assertEqual(r.summarize(p)['review_state'], 'reference')

    def test_export_preserves_data_and_never_merges_conditions(self):
        other = copy.deepcopy(self.data['points'][0])
        other['id'] = 'other-voltage'
        other['conditions']['supply_v'] = 5
        self.data['points'].append(other)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'report'
            rows = r.report(self.data, out)
            self.assertEqual(len(rows), 3)
            self.assertNotEqual(rows[0]['conditions'], rows[2]['conditions'])
            saved = json.loads((out / 'validated_input.json').read_text(encoding='utf-8'))
            self.assertEqual(saved, self.data)
            with (out / 'summary.csv').open(encoding='utf-8-sig', newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 3)
            with self.assertRaises(FileExistsError): r.report(self.data, out)

    def test_text_escaping_and_numeric_csv_values(self):
        self.assertEqual(r.csv_cell(' =1+1'), "' =1+1")
        self.assertEqual(r.csv_cell(-0.1), -0.1)
        self.assertNotIn('<script>', r.md('<script>|\n'))

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError): r.unique_object([('id', 1), ('id', 2)])


if __name__ == '__main__':
    unittest.main()
