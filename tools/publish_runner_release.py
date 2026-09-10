#!/usr/bin/env python3
"""Publish tested release assets using GitHub's API and an explicit User-Agent.

The workflow supplies GH_TOKEN. Tokens are never written to artifacts or logs.
Assets are staged on a draft and the release becomes public only when all
expected SHA-256 digests match. Existing different assets are never overwritten.
"""
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO = 'Kuberwastaken/math-gambling'
UA = 'OpenAI File Downloader, XaiImageApiFetch/1.0'
API = 'https://api.github.com/repos/' + REPO


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, *args, **kwargs):
        # API JSON and upload calls do not require a redirect. Never forward
        # the Authorization header to an asset CDN or an unexpected host.
        raise RuntimeError('Unexpected API redirect; publication stopped')


def api_request(token, method, url, payload=None, content_type='application/json'):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc not in ('api.github.com', 'uploads.github.com') or not parsed.path.startswith('/repos/' + REPO + '/'):
        raise RuntimeError('Unexpected GitHub API destination')
    if payload is not None and not isinstance(payload, bytes):
        payload = json.dumps(payload).encode('utf-8')
    headers = {'User-Agent': UA, 'Authorization': 'Bearer ' + token,
               'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
               'Content-Type': content_type}
    request = Request(url, data=payload, headers=headers, method=method)
    with build_opener(NoRedirect()).open(request, timeout=120) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise RuntimeError('GitHub API response exceeds cap')
    return json.loads(raw) if raw else None


def publish(root, tag, token, request=api_request):
    metadata = json.loads((root/'data/runner-release.json').read_text(encoding='utf-8'))
    version = metadata['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or tag != 'v' + version:
        raise RuntimeError('Tag must match the runner version')
    reference = request(token, 'GET', API + '/git/ref/tags/' + quote(tag, safe=''))
    target = reference['object']
    for _ in range(4):
        if target.get('type') != 'tag':
            break
        target = request(token, 'GET', API + '/git/tags/' + target['sha'])['object']
    if target.get('type') != 'commit' or (os.environ.get('GITHUB_SHA') and target.get('sha') != os.environ['GITHUB_SHA']):
        raise RuntimeError('Release tag differs from the commit tested by this workflow')
    archive = 'math-gambling-runner-v' + version + '.zip'
    expected = {name: (root/'release-assets'/name).read_bytes()
                for name in (archive, 'SHA256SUMS.txt', 'RUNNER_SETUP.md', 'runner-release.json')}
    checksums = {name: 'sha256:' + hashlib.sha256(raw).hexdigest() for name, raw in expected.items()}
    try:
        release = request(token, 'GET', API + '/releases/tags/' + quote(tag, safe=''))
    except HTTPError as exc:
        if exc.code != 404:
            raise
        exc.close()
        release = request(token, 'POST', API + '/releases',
                          {'tag_name': tag, 'name': 'Math Gambling runner ' + tag,
                           'draft': True, 'prerelease': False,
                           'body': (root/'docs/RUNNER_RELEASE_NOTES.md').read_text(encoding='utf-8')})
    release_id = release['id']
    if type(release_id) is not int or release_id <= 0 or release.get('tag_name') != tag:
        raise RuntimeError('Unexpected release identity')
    assets = request(token, 'GET', API + f'/releases/{release_id}/assets?per_page=100')
    by_name = {asset['name']: asset for asset in assets}
    if len(by_name) != len(assets):
        raise RuntimeError('Duplicate release asset names; inspect the draft')
    for name, raw in expected.items():
        existing = by_name.get(name)
        if existing:
            if existing.get('state') != 'uploaded' or existing.get('digest') != checksums[name] or existing.get('size') != len(raw):
                raise RuntimeError(f'Existing asset differs or is incomplete: {name}; refusing to overwrite it')
            continue
        if not release.get('draft'):
            raise RuntimeError('Published release is missing assets; refusing to alter an existing public version')
        uploaded = request(token, 'POST', f'https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets?name=' + quote(name, safe=''),
                           raw, 'application/zip' if name.endswith('.zip') else 'application/octet-stream')
        if uploaded.get('digest') != checksums[name] or uploaded.get('state') != 'uploaded' or uploaded.get('size') != len(raw):
            raise RuntimeError(f'Uploaded asset digest did not confirm: {name}; draft retained')
    if release.get('draft'):
        release = request(token, 'PATCH', API + f'/releases/{release_id}', {'draft': False})
    url = release.get('html_url', '')
    if url != f'https://github.com/{REPO}/releases/tag/{tag}':
        raise RuntimeError('Unexpected published release URL')
    return url


def main():
    root = Path(__file__).resolve().parents[1]
    token = os.environ.get('GH_TOKEN')
    tag = os.environ.get('GITHUB_REF_NAME', '')
    if not token:
        raise SystemExit('GH_TOKEN is required by the release workflow')
    try:
        print(publish(root, tag, token))
    except HTTPError as exc:
        raise SystemExit(f'GitHub API HTTP {exc.code}; existing assets and any draft are retained') from None
    except Exception as exc:
        raise SystemExit(f'Release not confirmed: {exc}') from None


if __name__ == '__main__':
    main()
