import copy
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import publish_snapshot_vps as publisher
import branch_state
from publish_snapshot_vps import validate_pair, ensure_newer, merge_pair, FILES
from export_mac import atomic_json
from export_mac import export


class PublishSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.root = root
        campaign=root/'lab/phase3/runs/campaign'
        campaign.mkdir(parents=True)
        (campaign/'status.json').write_text(json.dumps({'state':'running','updated_utc':'2026-09-10T10:00:00Z',
            'totals':{'curve_checks':12345678901234567890},'jobs':{'complete':1,'running':1},'solutions':[]}))
        self.pair=dict(zip(FILES,export(root/'lab',root/'public',now='2026-09-11T12:00:00Z')))

    def test_actual_export_validates(self):
        self.assertEqual(validate_pair(self.pair)[0]['totals']['curve_checks'],'12345678901234567890')

    def test_arbitrary_paths_rejected(self):
        with self.assertRaises(ValueError): validate_pair({**self.pair,'../../private':{}})

    def test_modified_or_mismatched_snapshot_rejected(self):
        for name,key,value in [(FILES[0],'snapshot_id','0'*64),(FILES[1],'snapshot_id','0'*64),
                               (FILES[0],'pid',777),(FILES[1],'samples',[])]:
            pair=copy.deepcopy(self.pair); pair[name][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): validate_pair(pair)

    def test_stale_time_and_regression_rejected(self):
        new=self.pair[FILES[0]]
        ensure_newer(new,new)
        for change in ({'updated_utc':'2026-09-09T10:00:00Z'}, {'totals':{'curve_checks':'1'}}):
            with self.assertRaises(ValueError): ensure_newer({**new,**change},new)

    def make_pair(self, stamp, count, suffix='next'):
        campaign = self.root / 'lab/phase3/runs/campaign/status.json'
        campaign.write_text(json.dumps({'state': 'running', 'updated_utc': stamp,
            'totals': {'curve_checks': count}, 'jobs': {'complete': 1, 'running': 1}, 'solutions': []}))
        return dict(zip(FILES, export(self.root / 'lab', self.root / suffix,
                                    now='2026-09-11T12:00:00Z')))

    def setup_remote(self, initial=None):
        self.repo = self.root / 'source'
        self.remote = self.root / 'remote.git'
        self.hooks = self.root / 'empty-hooks'
        self.hooks.mkdir()
        self.repo.mkdir()
        self.git('init', '--quiet', str(self.repo))
        self.git('init', '--quiet', '--bare', str(self.remote))
        self.git('config', 'user.name', 'Fixture', cwd=self.repo)
        self.git('config', 'user.email', 'fixture@example.invalid', cwd=self.repo)
        (self.repo / 'README.md').write_text('Trusted main remains unchanged.\n')
        self.git('add', '.', cwd=self.repo)
        self.git('commit', '--quiet', '-m', 'Main fixture', cwd=self.repo)
        self.git('branch', '-M', 'main', cwd=self.repo)
        self.git('remote', 'add', 'origin', str(self.remote), cwd=self.repo)
        self.git('push', '--quiet', 'origin', 'main', cwd=self.repo)
        self.main_before = self.git('rev-parse', 'main', cwd=self.repo).stdout.strip()
        self.git('checkout', '--quiet', '--orphan', 'cluster-data', cwd=self.repo)
        (self.repo / 'data/receipts').mkdir(parents=True)
        (self.repo / 'data/receipts/untouched.json').write_text('{"ledger":"must survive"}\n')
        if initial:
            for name in FILES: atomic_json(self.repo / name, initial[name])
        self.git('add', '.', cwd=self.repo)
        self.git('commit', '--quiet', '-m', 'Data fixture', cwd=self.repo)
        self.git('push', '--quiet', 'origin', 'cluster-data', cwd=self.repo)

    def git(self, *args, cwd=None):
        return subprocess.run(['git', '-c', 'core.hooksPath=' + str(self.root / 'empty-hooks'),
                               *args], cwd=cwd, text=True, capture_output=True, check=True)

    def receive(self, payload, race=None):
        original = publisher.git
        calls = []
        raced = False
        def fixture_git(*args, cwd=None):
            nonlocal raced
            # Isolate only our disposable fixture clones from machine-wide hooks.
            if cwd is not None:
                self.git('config', 'core.hooksPath', str(self.hooks), cwd=cwd)
            calls.append(args)
            if args[0] == 'push' and race is not None and not raced:
                raced = True
                race()
            return original(*args, cwd=cwd)
        with mock.patch.object(publisher, 'REMOTE', str(self.remote)), \
                mock.patch.object(publisher, 'git', side_effect=fixture_git):
            publisher.receive(payload)
        self.assertTrue(all('main' not in call for call in calls))
        self.assertIn('--single-branch', calls[0])
        self.assertEqual(self.git('rev-parse', 'main', cwd=self.remote).stdout.strip(), self.main_before)
        self.assertFalse(any(call[0] == 'rebase' or '--force' in call for call in calls))
        return calls

    def current_pair(self):
        return {name: json.loads(self.git('show', 'cluster-data:' + name,
                                        cwd=self.remote).stdout) for name in FILES}

    def commit_concurrent(self, pair=None):
        if pair:
            for name in FILES: atomic_json(self.repo / name, pair[name])
        (self.repo / 'data/receipts/concurrent.json').write_text('{"verified":true}\n')
        self.git('add', 'data', cwd=self.repo)
        self.git('commit', '--quiet', '-m', 'Concurrent accepted work', cwd=self.repo)
        self.git('push', '--quiet', 'origin', 'cluster-data', cwd=self.repo)

    def test_publish_only_data_branch_and_seed_missing_mac_pair(self):
        self.setup_remote()
        self.receive(self.pair)
        self.assertEqual(self.current_pair(), self.pair)
        changed = self.git('diff-tree', '--no-commit-id', '--name-only', '-r',
                           'cluster-data', cwd=self.remote).stdout.splitlines()
        self.assertEqual(sorted(changed), sorted(FILES))
        self.assertIn('must survive', self.git('show', 'cluster-data:data/receipts/untouched.json',
                                              cwd=self.remote).stdout)

    def test_same_pair_is_idempotent_and_richer_history_can_change_only_history(self):
        earlier = self.make_pair('2026-09-09T10:00:00Z', 50, 'earlier')
        self.setup_remote(self.pair)
        before = self.git('rev-parse', 'cluster-data', cwd=self.remote).stdout
        self.receive(self.pair)
        self.assertEqual(self.git('rev-parse', 'cluster-data', cwd=self.remote).stdout, before)
        enriched = merge_pair(self.pair, earlier)
        self.receive(enriched)
        self.assertEqual(len(self.current_pair()[FILES[1]]['samples']), 2)
        changed = self.git('diff-tree', '--no-commit-id', '--name-only', '-r',
                           'cluster-data', cwd=self.remote).stdout.splitlines()
        self.assertEqual(changed, [FILES[1]])

    def test_retry_preserves_concurrent_ledger_and_snapshot_history(self):
        initial = self.make_pair('2026-09-08T10:00:00Z', 1, 'initial')
        concurrent = self.make_pair('2026-09-09T10:00:00Z', 2, 'concurrent')
        incoming = self.make_pair('2026-09-10T10:00:00Z', 3, 'incoming')
        concurrent = merge_pair(concurrent, initial)
        self.setup_remote(initial)
        calls = self.receive(incoming, race=lambda: self.commit_concurrent(concurrent))
        self.assertEqual(sum(call[0] == 'push' for call in calls), 2)
        actual = self.current_pair()
        validate_pair(actual)
        self.assertEqual([row['totals']['curve_checks'] for row in actual[FILES[1]]['samples']],
                         ['1', '2', '3'])
        self.assertIn('verified', self.git('show', 'cluster-data:data/receipts/concurrent.json',
                                          cwd=self.remote).stdout)
        changed = self.git('diff-tree', '--no-commit-id', '--name-only', '-r',
                           'cluster-data', cwd=self.remote).stdout.splitlines()
        self.assertEqual(sorted(changed), sorted(FILES))

    def test_retry_refuses_to_overwrite_a_newer_concurrent_observation(self):
        initial = self.make_pair('2026-09-08T10:00:00Z', 1, 'initial')
        incoming = self.make_pair('2026-09-09T10:00:00Z', 2, 'incoming')
        newer = self.make_pair('2026-09-10T10:00:00Z', 3, 'newer')
        self.setup_remote(initial)
        with self.assertRaisesRegex(ValueError, 'newer public snapshot'):
            self.receive(incoming, race=lambda: self.commit_concurrent(newer))
        self.assertEqual(self.current_pair(), newer)

    def test_missing_data_branch_does_not_publish_to_main(self):
        self.setup_remote()
        self.git('update-ref', '-d', 'refs/heads/cluster-data', cwd=self.remote)
        with self.assertRaises(subprocess.CalledProcessError): self.receive(self.pair)
        self.assertEqual(self.git('rev-parse', 'main', cwd=self.remote).stdout.strip(), self.main_before)

    def test_incomplete_pair_and_symlink_are_rejected_before_writes(self):
        for kind in ('incomplete', 'symlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=self.root) as temporary:
                checkout = Path(temporary)
                if kind == 'incomplete': atomic_json(checkout / FILES[0], self.pair[FILES[0]])
                else:
                    outside = checkout / 'outside'; outside.mkdir()
                    (checkout / 'data').symlink_to(outside, target_is_directory=True)
                with self.assertRaises(ValueError): publisher.read_previous(checkout)

    def test_conflicting_history_and_older_same_observation_export_rejected(self):
        newer = self.make_pair('2026-09-10T10:00:00Z', 12345678901234567891)
        with self.assertRaisesRegex(ValueError, 'Conflicting historical'):
            merge_pair(newer, self.pair)
        snapshot = self.pair[FILES[0]]
        with self.assertRaisesRegex(ValueError, 'older export'):
            ensure_newer({**snapshot, 'exported_utc': '2000-01-01T00:00:00Z'}, snapshot)

    def test_overlay_keeps_only_the_two_optional_frozen_mac_files_before_first_seed(self):
        self.setup_remote()
        for name in FILES: atomic_json(self.repo / name, self.pair[name])
        (self.repo / 'data/strategy.json').write_text('{"old":true}')
        before = {name: (self.repo / name).read_bytes() for name in FILES}
        def empty_export(repo, ref, stage):
            (stage / 'data').mkdir()
        with mock.patch.object(branch_state, 'export_data', side_effect=empty_export), \
                mock.patch.object(branch_state, 'validate_snapshot'):
            branch_state.overlay(self.repo, 'HEAD')
        self.assertEqual({name: (self.repo / name).read_bytes() for name in FILES}, before)
        self.assertFalse((self.repo / 'data/strategy.json').exists())

    def test_overlay_rejects_half_a_mac_pair_without_touching_frozen_pair(self):
        self.setup_remote()
        for name in FILES: atomic_json(self.repo / name, self.pair[name])
        before = {name: (self.repo / name).read_bytes() for name in FILES}
        def partial_export(repo, ref, stage):
            atomic_json(stage / FILES[0], self.pair[FILES[0]])
        with mock.patch.object(branch_state, 'export_data', side_effect=partial_export), \
                mock.patch.object(branch_state, 'validate_snapshot'), \
                self.assertRaisesRegex(branch_state.BranchError, 'incomplete Mac snapshot pair'):
            branch_state.overlay(self.repo, 'HEAD')
        self.assertEqual({name: (self.repo / name).read_bytes() for name in FILES}, before)
        self.assertFalse(branch_state.state_path(self.repo).exists())
