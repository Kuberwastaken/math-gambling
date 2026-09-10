"""Release publication is tested with an in-memory API, never a real token."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import publish_runner_release as publisher


class RunnerReleaseTests(unittest.TestCase):
    def test_draft_upload_hashes_publish_and_safe_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('data', 'docs', 'release-assets'):
                (root/folder).mkdir()
            (root/'data/runner-release.json').write_text('{"version":"0.2.2"}')
            (root/'docs/RUNNER_RELEASE_NOTES.md').write_text('Release fixture')
            names = ('math-gambling-runner-v0.2.2.zip', 'SHA256SUMS.txt', 'RUNNER_SETUP.md', 'runner-release.json')
            for name in names:
                (root/'release-assets'/name).write_bytes(name.encode())
            state = {'release': None, 'assets': []}
            calls = []
            def request(token, method, url, payload=None, content_type=None):
                self.assertEqual(token, 'test-token')
                calls.append((method, url))
                if '/git/ref/tags/' in url:
                    return {'object': {'type': 'commit', 'sha': '1'*40}}
                if '/releases/tags/' in url:
                    if state['release'] is None:
                        raise HTTPError(url, 404, 'not found', {}, None)
                    return state['release'].copy()
                if method == 'POST' and url.endswith('/releases'):
                    self.assertTrue(payload['draft'])
                    state['release'] = {'id': 1, 'tag_name': 'v0.2.2', 'draft': True,
                                        'html_url': 'https://github.com/Kuberwastaken/math-gambling/releases/tag/v0.2.2'}
                    return state['release'].copy()
                if method == 'GET' and '/assets?' in url:
                    return state['assets']
                if method == 'POST' and 'uploads.github.com' in url:
                    asset = {'name': parse_qs(urlsplit(url).query)['name'][0], 'state': 'uploaded',
                             'size': len(payload), 'digest': 'sha256:'+hashlib.sha256(payload).hexdigest()}
                    state['assets'].append(asset)
                    return asset
                if method == 'PATCH':
                    self.assertEqual(len(state['assets']), 4)
                    self.assertEqual(payload, {'draft': False})
                    state['release']['draft'] = False
                    return state['release'].copy()
                self.fail(f'Unexpected request: {method} {url}')
            with patch.dict(os.environ, {'GITHUB_SHA': '1'*40}):
                url = publisher.publish(root, 'v0.2.2', 'test-token', request)
                self.assertTrue(url.endswith('/v0.2.2'))
                calls.clear()
                self.assertEqual(publisher.publish(root, 'v0.2.2', 'test-token', request), url)
                self.assertTrue(all(method == 'GET' for method, _ in calls))
                state['assets'][0]['digest'] = 'sha256:'+'0'*64
                with self.assertRaisesRegex(RuntimeError, 'refusing to overwrite'):
                    publisher.publish(root, 'v0.2.2', 'test-token', request)

    def test_unexpected_destination_cannot_receive_token(self):
        with self.assertRaisesRegex(RuntimeError, 'destination'):
            publisher.api_request('test-token', 'POST', 'https://example.org/upload', b'fixture')


if __name__ == '__main__':
    unittest.main()
