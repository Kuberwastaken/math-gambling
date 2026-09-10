#!/usr/bin/env python3
"""Validate generated internal links, required assets and portable download."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json,zipfile,hashlib
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'dist'/'math-gambling'
class Links(HTMLParser):
    def __init__(self):super().__init__();self.urls=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        for key in ['href','src']:
            if key in a:self.urls.append(a[key])
        if 'id'in a:self.ids.append(a['id'])
def main():
    errors=[];count=0
    for p in SITE.rglob('*.html'):
        parser=Links();parser.feed(p.read_text())
        if len(parser.ids)!=len(set(parser.ids)):errors.append(f'duplicate IDs {p.name}')
        for url in parser.urls:
            parsed=urlsplit(url)
            if parsed.scheme or parsed.netloc:continue
            path=unquote(parsed.path)
            if path.startswith('/math-gambling/'):
                target=SITE/path.removeprefix('/math-gambling/')
            elif path.startswith('/'):
                errors.append(f'outside project subpath: {url}');continue
            else:target=p.parent/path if path else p
            if target.is_dir():target=target/'index.html'
            if not target.is_file():errors.append(f'missing {url} in {p.relative_to(SITE)}')
            elif parsed.fragment:
                check=Links();check.feed(target.read_text())
                if parsed.fragment not in check.ids:errors.append(f'missing anchor {url}')
            count+=1
    required=['tools/runner.py','tools/search_core.py','data/site-config.json','data/strategy.json','LICENSE']
    with zipfile.ZipFile(SITE/'downloads/math-gambling-runner.zip') as z:
        for path in required:
            if 'math-gambling/'+path not in z.namelist():errors.append('download missing '+path)
    manifest=json.loads((SITE/'downloads/SHA256SUMS.json').read_text())
    for name,digest in manifest.items():
        if hashlib.sha256((SITE/'downloads'/name).read_bytes()).hexdigest()!=digest:errors.append('download checksum '+name)
    if errors:raise SystemExit('\n'.join(errors))
    print(f'{count} internal links/assets checked; runner files and download checksums passed.')
if __name__=='__main__':main()
