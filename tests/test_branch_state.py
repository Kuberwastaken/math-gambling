"""Generated branches stay separate from trusted source and the normal index."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import branch_state as branches
from coverage_index import publish_coverage
from ingest import atomic_json
from search_core import make_task, task_id


class BranchStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo, self.remote = self.root / 'source', self.root / 'remote.git'
        self.repo.mkdir()
        self.run_git('init', '-q', '-b', 'main')
        self.run_git('config', 'user.name', 'Fixture')
        self.run_git('config', 'user.email', 'fixture@example.test')
        # Local bare-repository tests must not invoke a developer's global
        # deployment/audit hooks. This does not change the real repository.
        (self.root / 'hooks').mkdir()
        self.run_git('config', 'core.hooksPath', str(self.root / 'hooks'))
        subprocess.run(['git', 'init', '--bare', '-q', str(self.remote)], check=True, capture_output=True)
        self.run_git('remote', 'add', 'origin', str(self.remote))
        (self.repo / 'README.md').write_text('Trusted main README\n', encoding='utf-8')
        (self.repo / 'tools').mkdir()
        (self.repo / 'tools/trusted.py').write_text('MAIN_CODE = True\n', encoding='utf-8')
        (self.repo / 'data').mkdir()
        for name in ('cluster', 'strategy', 'site-config', 'mac', 'mac-history', 'runner-release'):
            (self.repo / f'data/{name}.json').write_text('{}\n', encoding='utf-8')
        publish_coverage(self.repo / 'data', [])
        self.run_git('add', '.')
        self.run_git('commit', '-qm', 'Trusted frozen bootstrap')
        self.source = self.run_git('rev-parse', 'HEAD')

    def tearDown(self):
        self.temporary.cleanup()

    def run_git(self, *args):
        result = subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True, text=True)
        if result.returncode: raise AssertionError(result.stderr)
        return result.stdout.strip()

    def render(self, repo, destination, **_):
        Path(destination).write_text((Path(repo) / 'README.md').read_text() + 'Rendered from trusted source.\n')

    def initialize(self):
        with mock.patch.object(branches, 'render_readme', self.render):
            return branches.init_data(self.repo, self.source)['commit']

    def install_ledger(self):
        task = make_task('c00', 0)
        record = dict(schema='math-gambling-verified-task-v1', sequence=1,
                      result=dict(task=task, id=task_id(task)), fixture='immutable')
        path = self.repo / 'data/receipts/tasks/00/fixture.json'
        atomic_json(path, record)
        hit = self.repo / 'data/receipts/hits/00/fixture.json'
        atomic_json(hit, {'fixture': 'immutable discovery record'})
        publish_coverage(self.repo / 'data', [record])
        self.run_git('add', 'data'); self.run_git('commit', '-qm', 'Accepted fixture ledger')
        self.source = self.run_git('rev-parse', 'HEAD')
        return path, hit

    def test_explicit_bootstrap_is_orphan_and_overlay_does_not_import_source_or_readme(self):
        commit = self.initialize()
        self.assertEqual(self.run_git('rev-list', '--parents', '-n', '1', commit), commit)
        paths = branches.entries(self.repo, commit)
        self.assertTrue(all(branches.generated(path) or path == 'README.md' for path in paths))
        self.assertNotIn('data/site-config.json', paths)
        self.assertNotIn('tools/trusted.py', paths)
        stale = self.repo / 'data/learning/stale.json'
        stale.parent.mkdir(); stale.write_text('{}')
        before_readme = (self.repo / 'README.md').read_bytes()
        before_index = (self.repo / '.git/index').read_bytes()
        branches.overlay(self.repo, commit)
        self.assertFalse(stale.exists(), 'overlay must remove data retired by the authoritative branch')
        self.assertEqual((self.repo / 'README.md').read_bytes(), before_readme)
        self.assertEqual((self.repo / '.git/index').read_bytes(), before_index)
        self.assertEqual((self.repo / 'tools/trusted.py').read_text(), 'MAIN_CODE = True\n')
        self.assertTrue((self.repo / 'data/mac.json').exists())

    def test_missing_branch_and_incomplete_payload_fail_closed(self):
        with self.assertRaisesRegex(branches.BranchError, 'missing'):
            branches.fetch_branch(self.repo, branches.DATA_BRANCH)
        stage = self.root / 'incomplete'; stage.mkdir()
        (stage / 'README.md').write_text('Only a README')
        commit, _ = branches.snapshot_commit(self.repo, stage, None, 'Incomplete fixture')
        before = (self.repo / 'data/cluster.json').read_bytes()
        with self.assertRaisesRegex(branches.BranchError, 'incomplete'):
            branches.overlay(self.repo, commit)
        self.assertEqual((self.repo / 'data/cluster.json').read_bytes(), before)

    def test_branch_code_symlinks_and_destination_symlinks_are_rejected(self):
        original = self.initialize()
        stage = self.root / 'bad-data'; stage.mkdir()
        branches.export_data(self.repo, original, stage)
        (stage / 'tools').mkdir(); (stage / 'tools/injected.py').write_text('UNTRUSTED = True')
        commit, _ = branches.snapshot_commit(self.repo, stage, None, 'Code injection fixture')
        with self.assertRaisesRegex(branches.BranchError, 'non-data path'):
            branches.overlay(self.repo, commit)
        shutil.rmtree(stage / 'tools')
        (stage / 'data/cluster.json').unlink()
        (stage / 'data/cluster.json').symlink_to('../../README.md')
        commit, _ = branches.snapshot_commit(self.repo, stage, None, 'Symlink fixture')
        with self.assertRaisesRegex(branches.BranchError, 'regular'):
            branches.overlay(self.repo, commit)
        outside = self.root / 'outside'; outside.mkdir()
        shutil.rmtree(self.repo / 'data/coverage')
        (self.repo / 'data/coverage').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(branches.BranchError, 'symlink'):
            branches.overlay(self.repo, original)
        self.assertEqual(list(outside.iterdir()), [])

    def test_publish_data_keeps_main_and_index_unchanged_and_renders_main_readme(self):
        initial = self.initialize()
        branches.overlay(self.repo, initial)
        main_readme = (self.repo / 'README.md').read_bytes()
        main_index = (self.repo / '.git/index').read_bytes()
        (self.repo / 'data/cluster.json').write_text('{"new":true}\n')
        with mock.patch.object(branches, 'render_readme', self.render):
            published = branches.publish_data(self.repo)
            repeated = branches.publish_data(self.repo)
        self.assertTrue(published['changed'])
        self.assertEqual(published['parent'], initial)
        self.assertEqual(self.run_git('rev-parse', 'HEAD'), self.source)
        self.assertEqual((self.repo / 'README.md').read_bytes(), main_readme)
        self.assertEqual((self.repo / '.git/index').read_bytes(), main_index)
        self.assertEqual(self.run_git('show', published['commit'] + ':README.md'),
                         'Trusted main README\nRendered from trusted source.')
        self.assertEqual(self.run_git('rev-parse', published['commit'] + '^{tree}'),
                         self.run_git('rev-parse', repeated['commit'] + '^{tree}'))
        self.run_git('commit', '--allow-empty', '-qm', 'Source changed')
        with self.assertRaisesRegex(branches.BranchError, 'Source changed'):
            branches.publish_data(self.repo)

    def test_interrupted_overlay_invalidates_an_earlier_publication_token(self):
        initial = self.initialize()
        branches.overlay(self.repo, initial)
        copy = shutil.copyfile
        def interrupted(source, target, *args, **kwargs):
            if Path(target).resolve() == (self.repo / 'data/strategy.json').resolve():
                raise OSError('fixture interrupted replacement')
            return copy(source, target, *args, **kwargs)
        with mock.patch.object(branches.shutil, 'copyfile', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                branches.overlay(self.repo, initial)
        self.assertFalse(branches.state_path(self.repo).exists())
        with self.assertRaisesRegex(branches.BranchError, 'Overlay the authoritative'):
            branches.publish_data(self.repo)

    def test_existing_remote_cannot_be_reinitialized_or_overwritten_by_stale_publisher(self):
        initial = self.initialize()
        self.run_git('push', '-q', 'origin', initial + ':refs/heads/cluster-data')
        with self.assertRaisesRegex(branches.BranchError, 'already exists'):
            branches.init_data(self.repo, self.source)
        branches.overlay(self.repo, branches.fetch_branch(self.repo, branches.DATA_BRANCH))
        with mock.patch.object(branches, 'render_readme', self.render):
            (self.repo / 'data/cluster.json').write_text('{"first":true}')
            first = branches.publish_data(self.repo, push=True)
            (self.repo / 'data/cluster.json').write_text('{"second":true}')
            with self.assertRaises(branches.BranchError): branches.publish_data(self.repo, push=True)
        self.assertEqual(branches.fetch_branch(self.repo, branches.DATA_BRANCH), first['commit'])
        self.assertEqual(self.run_git('rev-parse', 'HEAD'), self.source)

    def test_site_snapshot_is_orphan_and_contains_only_built_files(self):
        stage = self.root / 'built'; stage.mkdir()
        (stage / 'index.html').write_text('<!doctype html><title>Fixture</title>')
        (stage / 'app.mjs').write_text('export const built=true;')
        result = branches.publish_site(self.repo, stage)
        self.assertEqual(set(branches.entries(self.repo, result['commit'])), {'index.html', 'app.mjs'})
        self.assertIsNone(result['parent'])
        self.assertEqual(self.run_git('rev-parse', 'HEAD'), self.source)

    def test_snapshot_cannot_keep_coverage_while_losing_accepted_task_records(self):
        task, _ = self.install_ledger()
        initial = self.initialize()
        branches.overlay(self.repo, initial)
        task.unlink()
        with mock.patch.object(branches, 'render_readme', self.render):
            with self.assertRaisesRegex(branches.BranchError, 'ledger and exact coverage disagree'):
                branches.publish_data(self.repo)
        self.run_git('add', 'data'); self.run_git('commit', '-qm', 'Incomplete bootstrap fixture')
        with mock.patch.object(branches, 'render_readme', self.render):
            with self.assertRaisesRegex(branches.BranchError, 'ledger and exact coverage disagree'):
                branches.init_data(self.repo, 'HEAD')

    def test_accepted_task_and_discovery_blobs_are_append_only(self):
        task, hit = self.install_ledger()
        initial = self.initialize()
        branches.overlay(self.repo, initial)
        original = task.read_bytes()
        task.write_bytes(original.replace(b'immutable', b'modified'))
        with mock.patch.object(branches, 'render_readme', self.render):
            with self.assertRaisesRegex(branches.BranchError, 'append-only'):
                branches.publish_data(self.repo)
            task.write_bytes(original)
            hit.unlink()
            with self.assertRaisesRegex(branches.BranchError, 'append-only'):
                branches.publish_data(self.repo)

    def test_relative_source_links_move_to_main_but_generated_data_stays_live(self):
        (self.repo / 'docs').mkdir()
        source = ('[Docs](docs/BRANCHES.md) ![Chart](data/readme-progress.svg) '
                  '[Mac](data/mac.json) [Ledger](data/receipts/) [Source](tools/trusted.py) '
                  '[Here](#here) [Remote](https://example.test)\n'
                  '```sh\n[literal](tools/example.py)\n```\n')
        rendered = branches.rewrite_readme_links(source, self.repo)
        self.assertIn('/blob/main/docs/BRANCHES.md)', rendered)
        self.assertIn('[Mac](data/mac.json)', rendered)
        self.assertIn('/blob/main/tools/trusted.py)', rendered)
        self.assertIn('](data/readme-progress.svg)', rendered)
        self.assertIn('](data/receipts/)', rendered)
        self.assertIn('[Here](#here)', rendered)
        self.assertIn('[literal](tools/example.py)', rendered)

    def test_source_workflows_keep_data_writes_and_deploy_cadence_separate(self):
        root = Path(__file__).resolve().parents[1]
        verifier = (root / '.github/workflows/cluster.yml').read_text()
        pages = (root / '.github/workflows/pages.yml').read_text()
        self.assertIn('branch_state.py overlay --fetch', verifier)
        self.assertIn('branch_state.py publish-data --push', verifier)
        self.assertNotIn('git pull --rebase', verifier)
        self.assertNotIn('git add --', verifier)
        self.assertIn("cron: '7,27,47 * * * *'", pages)
        self.assertNotIn('workflow_run:', pages)
        self.assertNotIn('  push:', pages)
        self.assertIn('publish-site --directory dist/math-gambling --push', pages)
        self.assertIn('ref: ${{ needs.build.outputs.site_commit }}', pages)
        self.assertIn('path: published-site', pages)
        self.assertNotIn('path: dist/math-gambling', pages)


if __name__ == '__main__': unittest.main()
