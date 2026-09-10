"""Public snapshot tests use synthetic observations, never a fabricated 114 solution."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.export_mac import compact_history, export, identities, integer, sample


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lab = self.root / 'lab'
        self.campaign = self.lab / 'phase3/runs/campaign'
        self.campaign.mkdir(parents=True)
        self.output = self.root / 'public'
        self.status = {'state': 'running', 'updated_utc': '2026-09-10T01:00:00Z',
                       'totals': {'curve_checks': 2**80, 'exact_tests': 123},
                       'jobs': {'complete': 91, 'running': 2}, 'solutions': [],
                       'pid': 77777, 'path': '/Users/private/person', 'token': 'SECRET',
                       'learning_gate': {'enable_model': True, 'spearman': .8,
                                         'top_quarter_over_baseline': 1.3,
                                         'secret': 'SECRET'}}
        self.write_status()

    def write_status(self):
        (self.campaign / 'status.json').write_text(json.dumps(self.status))

    def run_export(self):
        return export(self.lab, self.output, now='2026-09-10T01:01:00Z')

    def test_allowlist_and_exact_large_counts(self):
        result, history = self.run_export()
        text = json.dumps([result, history])
        for private in ('77777', '/Users/', 'SECRET', '"pid"', '"token"'):
            self.assertNotIn(private, text)
        self.assertEqual(result['totals']['curve_checks'], str(2**80))
        self.assertEqual(result['jobs']['complete'], '91')
        self.assertIsNone(result['learning']['success_probability'])
        self.assertFalse(result['is_live'])
        self.assertEqual(result['snapshot_id'], history['snapshot_id'])

    def test_calibration_rows_are_bounded_and_allowlisted(self):
        valid = {'key':'offset:1:0:0:0:64','predicted_utility':12.5,'observed_utility':13.1,'token':'SECRET'}
        self.status['learning_gate']['rows'] = [valid, {'key':'/Users/private/person','predicted_utility':2,'observed_utility':3}, {'key':'offset:1:0:0:0:64','predicted_utility':float('nan'),'observed_utility':3}]
        self.write_status()
        result, _ = self.run_export()
        rows = result['learning']['holdout']['rows']
        self.assertEqual(rows, [{'context':'offset:1:0:0:0:64','predicted':12.5,'observed':13.1}])
        self.assertNotIn('SECRET', json.dumps(rows))
        self.status['learning_gate']['rows'] = [valid] * 100
        self.write_status()
        self.assertEqual(len(self.run_export()[0]['learning']['holdout']['rows']), 81)

    def test_source_tree_unchanged_and_database_untouched(self):
        forbidden = self.campaign / 'campaign.sqlite3'
        forbidden.write_bytes(b'not a database; must never be opened by exporter')
        before = {str(p.relative_to(self.lab)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.lab.rglob('*') if p.is_file()}
        self.run_export()
        after = {str(p.relative_to(self.lab)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.lab.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_invalid_identity_blocks_export(self):
        # A genuine identity for k=3 is not a solution of k=114.
        self.status['solutions'] = [[4, 4, -5]]
        self.write_status()
        with self.assertRaises(ValueError): self.run_export()
        self.assertFalse((self.output / 'mac.json').exists())
        self.assertEqual(identities([]), [])

    def test_counter_types_fail_closed(self):
        for value in (1.0, True, -1, '1e20', '01'):
            with self.subTest(value=value), self.assertRaises(ValueError): integer(value)
        bad = dict(self.status, totals={'curve_checks': 1.1})
        with self.assertRaises(ValueError): sample(bad)

    def test_history_is_genuine_bounded_and_not_interpolated(self):
        lines = []
        for i in range(600):
            stamp = f'2026-09-10T00:{i // 60:02}:{i % 60:02}Z'
            lines.append(f'{stamp} running: {i:,} curve checks; 0 verified solutions\n')
        (self.campaign / 'process.log').write_text('private unrelated log line\n' + ''.join(lines))
        _, history = self.run_export()
        self.assertEqual(len(history['samples']), 300)
        genuine = {line.split()[0] for line in lines} | {self.status['updated_utc']}
        self.assertTrue(all(row['updated_utc'] in genuine for row in history['samples']))
        self.assertNotIn('exact_tests', history['samples'][0]['totals'])

    def test_latest_audit_is_allowlisted_and_not_current_claim(self):
        old = self.lab / 'research-2026-09-09/production-audit.json'
        old.parent.mkdir()
        old.write_text(json.dumps({'observed_utc': '2026-09-09T00:00:00Z',
                                   'database_integrity': 'ok', 'pid': 55555}))
        (self.campaign / 'heartbeat-health.json').write_text(json.dumps({
            'audited_utc': '2026-09-10T00:30:00Z', 'pid': 66666,
            'sources_match': True, 'audit': {'database_integrity': 'ok',
                                           'complete_tiles': 80, 'private': 'SECRET'}}))
        result, _ = self.run_export()
        self.assertEqual(result['audit']['observed_utc'], '2026-09-10T00:30:00Z')
        self.assertEqual(result['audit']['complete_tiles'], '80')
        self.assertNotIn('private', result['audit'])
        self.assertEqual(result['jobs']['complete'], '91')

    def test_regression_and_stale_source_preserve_public_files(self):
        self.run_export()
        before = (self.output / 'mac.json').read_bytes()
        self.status['updated_utc'] = '2026-09-09T01:00:00Z'
        self.write_status()
        with self.assertRaises(ValueError): self.run_export()
        self.assertEqual(before, (self.output / 'mac.json').read_bytes())
        self.status['updated_utc'] = '2026-09-10T02:00:00Z'
        self.status['totals']['curve_checks'] = 1
        self.write_status()
        with self.assertRaises(ValueError): self.run_export()
        self.assertEqual(before, (self.output / 'mac.json').read_bytes())

    def test_reject_destination_inside_live_lab(self):
        with self.assertRaises(ValueError): export(self.lab, self.lab / 'data')


if __name__ == '__main__':
    unittest.main()
