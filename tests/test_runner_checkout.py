"""Exercise Git's Windows-style checkout without weakening byte-hash checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import client_audit
import coverage_index
import ingest
import runner


class RunnerCheckoutTests(unittest.TestCase):
    def test_autocrlf_checkout_preserves_all_coverage_and_archive_bytes(self):
        with tempfile.TemporaryDirectory(prefix='mg114 Windows checkout ') as directory:
            source = Path(directory)/'source'
            checkout = Path(directory)/'checkout'
            source.mkdir()
            # Ignore the host's identity, hooks and signing defaults in this
            # disposable fixture repository; the actual project is not changed.
            env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_TERMINAL_PROMPT='0')
            def git(*args, cwd=source):
                result = subprocess.run(['git', *args], cwd=cwd, env=env,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                return result.stdout
            git('init', '--quiet', '--initial-branch=main')
            attributes = (ROOT/'.gitattributes').read_text(encoding='utf-8')
            # The control opts out of the project's LF policy, proving that
            # core.autocrlf=true really performs CRLF checkout in this test.
            (source/'.gitattributes').write_text(attributes+'\nnewline-control.txt text !eol\n', encoding='utf-8', newline='\n')
            raw_control = b'first line\nsecond line\n'
            (source/'newline-control.txt').write_bytes(raw_control)
            (source/'ordinary.py').write_bytes(b'print("source uses LF")\n')
            archived = source/'research/archive/original.txt'
            archived.parent.mkdir(parents=True)
            archived.write_bytes(b'original archived bytes\r\nkeep their original endings\r\n')
            coverage_dir = source/'data/coverage'
            coverage_dir.mkdir(parents=True)
            original, _ = coverage_index.read_coverage(ROOT/'data/coverage')
            names = ['index.json', *(entry['file'] for entry in original['shards'].values())]
            for name in names:
                shutil.copyfile(ROOT/'data/coverage'/name, coverage_dir/name)
            git('-c', 'core.autocrlf=false', 'add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'commit.gpgSign=false', 'commit', '--quiet', '-m', 'Byte preservation fixture')
            git('-c', 'core.autocrlf=true', 'clone', '--quiet', '--no-local', str(source), str(checkout), cwd=Path(directory))
            self.assertEqual((checkout/'newline-control.txt').read_bytes(), raw_control.replace(b'\n', b'\r\n'))
            self.assertEqual((checkout/'ordinary.py').read_bytes(), (source/'ordinary.py').read_bytes())
            self.assertEqual((checkout/'research/archive/original.txt').read_bytes(), archived.read_bytes())
            checked, _ = coverage_index.read_coverage(checkout/'data/coverage')
            self.assertEqual(checked, original)
            for context, entry in checked['shards'].items():
                with self.subTest(context=context):
                    raw = (checkout/'data/coverage'/entry['file']).read_bytes()
                    self.assertEqual(raw, (coverage_dir/entry['file']).read_bytes())
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['sha256'])

    def test_protocol_and_audit_writers_emit_utf8_lf(self):
        with tempfile.TemporaryDirectory(prefix='mg114 LF writers ') as directory:
            out = Path(directory)
            value = {'label': 'Δ', 'first': 114}
            ingest.atomic_json(out/'published.json', value)
            expected = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)+'\n').encode('utf-8')
            self.assertEqual((out/'published.json').read_bytes(), expected)
            runner.atomic_json(out/'local.json', value)
            self.assertNotIn(b'\r', (out/'local.json').read_bytes())
            self.assertTrue((out/'local.json').read_bytes().endswith(b'\n'))
            audit = client_audit.RunAudit(out, '11'*32, {'workers': 1})
            audit.write('test', count=1)
            raw = audit.path.read_bytes()
            self.assertNotIn(b'\r', raw)
            self.assertEqual(len(raw.splitlines()), 2)


if __name__ == '__main__':
    unittest.main()
