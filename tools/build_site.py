#!/usr/bin/env python3
"""Dependency-free, escaped static build; deployed directory is dist/math-gambling."""
from pathlib import Path
import hashlib, html, json, re, shutil, zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'/'math-gambling'
BASE='/math-gambling/'
VERSION=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'web').glob('*')) if p.is_file())).hexdigest()[:12]

def shell(title, body, active=''):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{"Math Gambling" if not active else html.escape(title)+" · Math Gambling"}</title><meta name="description" content="An open search for x³ + y³ + z³ = 114. Contribute processor time, watch exact computations, and help test our strategy. The odds are unknown.">
<meta name="theme-color" content="#132d25"><meta property="og:title" content="Math Gambling — let it ride"><meta property="og:description" content="An open mathematical long shot. Real computation. Unknown odds."><meta property="og:type" content="website"><meta property="og:image" content="https://kuber.studio/math-gambling/assets/social.svg">
<link rel="icon" href="{BASE}assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="{BASE}styles.css?v={VERSION}"><link rel="canonical" href="https://kuber.studio{BASE}{active}">
<script type="module" src="{BASE}app.mjs?v={VERSION}"></script></head><body data-page="{active or 'home'}">
<a class="skip" href="#main">Skip to content</a>{'<div class="back-to-table"><a href="'+BASE+'">← Back to the table</a></div>' if active else ''}
<main id="main">{body}</main><footer><a class="wordmark" href="{BASE}">Math Gambling</a><div><a href="{BASE}approach/">The approach</a><a href="{BASE}cluster/">The cluster</a><a href="{BASE}paper/">The paper</a><a href="{BASE}research/">The notebook</a><a href="https://github.com/Kuberwastaken/math-gambling">GitHub ↗</a></div></footer>
<noscript><p class="noscript">The research is readable without JavaScript. Browser computation requires JavaScript and starts only when you choose to run it.</p></noscript></body></html>'''

def markdown(text):
    # This is a small safe reader, not a complete Markdown/LaTeX implementation.
    lines=[]; buf=[]; code=False
    def inline(t):
        t=html.escape(t)
        t=re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',r'<a href="\2" rel="noreferrer">\1</a>',t)
        t=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',t)
        return re.sub(r'`([^`]+)`',r'<code>\1</code>',t)
    def flush():
        if buf: lines.append('<p>'+inline(' '.join(buf))+'</p>');buf.clear()
    for line in text.splitlines():
        if line.startswith('```'):
            flush();lines.append('</code></pre>' if code else '<pre><code>');code=not code
        elif code:lines.append(html.escape(line)+'\n')
        elif not line.strip():flush()
        elif re.match(r'^#{1,6} ',line):
            flush();level=min(4,len(line)-len(line.lstrip('#'))+1);lines.append(f'<h{level}>'+inline(line.lstrip('# '))+f'</h{level}>')
        elif line.startswith(('- ','* ')):
            flush();lines.append('<p class="note-bullet">• '+inline(line[2:])+'</p>')
        else:buf.append(line)
    flush()
    if code:lines.append('</code></pre>')
    return '\n'.join(lines)

def main():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (ROOT/'dist'/'.nojekyll').touch()
    (ROOT/'dist'/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=math-gambling/"><a href="math-gambling/">math-gambling</a>')
    for source in (ROOT/'web').iterdir():
        if source.name=='pages':continue
        if source.is_dir():shutil.copytree(source,OUT/source.name)
        else:shutil.copy2(source,OUT/source.name)
    # A returning browser must not combine new markup with a cached old worker UI.
    for module in OUT.glob('*.mjs'):
        content=module.read_text()
        for asset in ('engine.mjs','live-viz.mjs','search-worker.mjs'):
            for prefix in ('./',''):
                for quote in ('"', "'"):
                    content=content.replace(quote+prefix+asset+quote, quote+prefix+asset+'?v='+VERSION+quote)
        module.write_text(content)
    for name,title,path in [('home','The table',''),('approach','The approach','approach/'),('cluster','The cluster','cluster/'),('paper','A paper, unfinished','paper/'),('research','The notebook','research/')]:
        source=ROOT/'web'/'pages'/f'{name}.html'
        if not source.exists():continue
        dest=OUT/path;dest.mkdir(parents=True,exist_ok=True)
        (dest/'index.html').write_text(shell(title,source.read_text().replace('{{BASE}}',BASE),path))
    (OUT/'data').mkdir()
    for name in ['site-config.json','mac.json','mac-history.json','cluster.json','strategy.json']:
        p=ROOT/'data'/name
        if p.exists():json.loads(p.read_text());shutil.copy2(p,OUT/'data'/name)
    articles={
      'RESEARCH':'docs/RESEARCH.md','CLUSTER':'docs/CLUSTER.md','PROTOCOL':'docs/PROTOCOL.md','ARCHIVE':'docs/ARCHIVE.md',
      'SEARCH_VERDICT':'research/archive/research-2026-09-09/SEARCH_VERDICT.md',
      'ALGORITHM_REVIEW':'research/archive/research-2026-09-09/ALGORITHM_REVIEW.md',
      'GEOMETRY_REVIEW':'research/archive/research-2026-09-09/GEOMETRY_REVIEW.md',
      'DISCOVERY_LEARNING':'research/archive/research-2026-09-09/DISCOVERY_LEARNING.md',
      'DOMAIN_PROOF':'research/archive/phase3/DOMAIN_PROOF.md'}
    for slug,rel in articles.items():
        p=ROOT/rel
        if not p.exists():continue
        dest=OUT/'research'/slug.lower();dest.mkdir(parents=True,exist_ok=True)
        content=f'<article class="article"><a class="back-link" href="{BASE}research/">← The notebook</a><h1>{slug.replace("_"," ").title()}</h1><p class="reading-note">Research notes. Mathematical notation is preserved in plain text; <a href="https://github.com/Kuberwastaken/math-gambling/blob/main/{rel}">read the source on GitHub</a> for full Markdown formatting.</p>'+markdown(p.read_text())+'</article>'
        (dest/'index.html').write_text(shell(slug.replace('_',' ').title(),content,'research/'))
    downloads=OUT/'downloads';downloads.mkdir()
    local_files=['tools/runner.py','tools/search_core.py','data/strategy.json','data/site-config.json','docs/PROTOCOL.md','README.md','LICENSE']
    with zipfile.ZipFile(downloads/'math-gambling-runner.zip','w',zipfile.ZIP_DEFLATED) as z:
        for rel in local_files:
            if (ROOT/rel).exists():z.write(ROOT/rel,'math-gambling/'+rel)
    for p in (ROOT/'paper').glob('*.tex'):shutil.copy2(p,downloads/p.name)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in downloads.iterdir() if p.is_file()}
    (downloads/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (OUT/'404.html').write_text(shell('Page not found',f'<section class="article"><h1>This branch is empty.</h1><p>There is no page here. <a href="{BASE}">Return to the table.</a></p></section>'))
    print(f'Built {len(list(OUT.rglob("*")))} entries in {OUT.relative_to(ROOT)}')
if __name__=='__main__':main()
