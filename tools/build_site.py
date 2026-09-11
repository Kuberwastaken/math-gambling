#!/usr/bin/env python3
"""Static build with pre-rendered Markdown and math; output is dist/math-gambling."""
from pathlib import Path
import hashlib, html, json, shutil, subprocess, zipfile
from coverage_index import read_coverage, referenced_files
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'/'math-gambling'
BASE='/math-gambling/'
VERSION=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'web').rglob('*')) if p.is_file()) + (ROOT/'package-lock.json').read_bytes()).hexdigest()[:12]

def shell(title, body, active='', math=False):
    math_css = f'<link rel="stylesheet" href="{BASE}assets/katex/katex.min.css?v={VERSION}">' if math else ''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{"Math Gambling" if not active else html.escape(title)+" · Math Gambling"}</title><meta name="description" content="Join a volunteer computing search for three integers whose cubes add up to 114. Run exact computations in your browser or contribute with the local runner.">
<meta name="color-scheme" content="only light"><meta name="theme-color" content="#ffffff"><meta property="og:title" content="Math Gambling"><meta property="og:description" content="Join a volunteer computing search for three integers whose cubes add up to 114. Run exact computations in your browser or contribute with the local runner."><meta property="og:type" content="website"><meta property="og:image" content="https://kuber.studio/math-gambling/assets/social.png?v={VERSION}">
<meta property="og:image:type" content="image/png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="MATH GAMBLING in black Georgia lettering beside a cropped red and black roulette wheel."><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="Math Gambling"><meta name="twitter:description" content="Join a volunteer computing search for three integers whose cubes add up to 114. Run exact computations in your browser or contribute with the local runner."><meta name="twitter:image" content="https://kuber.studio/math-gambling/assets/social.png?v={VERSION}">
{math_css}<link rel="icon" href="{BASE}assets/favicon.svg?v={VERSION}" type="image/svg+xml"><link rel="stylesheet" href="{BASE}styles.css?v={VERSION}"><link rel="canonical" href="https://kuber.studio{BASE}{active}">
<script type="module" src="{BASE}app.mjs?v={VERSION}"></script></head><body data-page="{active or 'home'}">
<a class="skip" href="#main">Skip to content</a><nav class="plain-nav" aria-label="Main"><a href="{BASE}">Home</a><a href="{BASE}#leaderboard">Leaderboard</a><a href="{BASE}approach/">Approach</a><a href="{BASE}#learning">Learning</a><a href="{BASE}paper/">Paper</a><a href="{BASE}research/">Research</a><a href="https://github.com/Kuberwastaken/math-gambling">GitHub</a></nav>
<main id="main">{body}</main><footer><a class="wordmark" href="{BASE}">Math Gambling</a><div><a href="{BASE}approach/">The approach</a><a href="{BASE}cluster/">The cluster</a><a href="{BASE}paper/">The paper</a><a href="{BASE}research/">The notebook</a><a href="https://github.com/Kuberwastaken/math-gambling">GitHub ↗</a></div></footer>
<noscript><p class="noscript">The research is readable without JavaScript. Browser computation requires JavaScript and starts only when you choose to run it.</p></noscript></body></html>'''

def render_research(articles):
    published = {rel: BASE + 'research/' + slug.lower() + '/' for slug, rel in articles.items()}
    request = {'published': published, 'articles': [
        {'source': rel, 'text': (ROOT / rel).read_text(encoding='utf-8')} for rel in articles.values()
    ]}
    result = subprocess.run(['node', str(ROOT / 'tools/render_research.mjs')],
                            input=json.dumps(request), text=True, encoding='utf-8', capture_output=True, cwd=ROOT)
    if result.returncode:
        raise SystemExit('Research rendering failed. Run npm ci --ignore-scripts before building.\n' + result.stderr)
    return {entry['source']: entry for entry in json.loads(result.stdout)}


def main():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (ROOT/'dist'/'.nojekyll').touch()
    (ROOT/'dist'/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=math-gambling/"><a href="math-gambling/">math-gambling</a>', encoding='utf-8')
    for source in (ROOT/'web').iterdir():
        if source.name=='pages':continue
        if source.is_dir():shutil.copytree(source,OUT/source.name)
        else:shutil.copy2(source,OUT/source.name)
    # A returning browser must not combine new markup with a cached old worker UI.
    for module in OUT.glob('*.mjs'):
        content=module.read_text(encoding='utf-8')
        for asset in sorted(p.name for p in OUT.glob('*.mjs')):
            for prefix in ('./',''):
                for quote in ('"', "'"):
                    content=content.replace(quote+prefix+asset+quote, quote+prefix+asset+'?v='+VERSION+quote)
        module.write_text(content, encoding='utf-8')
    for name,title,path in [('home','The table',''),('approach','The approach','approach/'),('cluster','The cluster','cluster/'),('paper','A paper, unfinished','paper/'),('research','The notebook','research/')]:
        source=ROOT/'web'/'pages'/f'{name}.html'
        if not source.exists():continue
        dest=OUT/path;dest.mkdir(parents=True,exist_ok=True)
        body=source.read_text(encoding='utf-8')
        if '{{PAPER_PREVIEW}}' in body:
            paper=(ROOT/'web/pages/paper.html').read_text(encoding='utf-8')
            manuscript=paper[paper.index('<article class="manuscript"'):paper.index('</article>')+10]
            body=body.replace('{{PAPER_PREVIEW}}',manuscript)
        (dest/'index.html').write_text(shell(title,body.replace('{{BASE}}',BASE),path), encoding='utf-8')
    (OUT/'data').mkdir()
    for name in ['site-config.json','mac.json','mac-history.json','cluster.json','strategy.json','runner-release.json']:
        p=ROOT/'data'/name
        if p.exists():
            if name == 'cluster.json':
                from public_reports import publish
                publish(p, OUT/'data'/name)
            else:
                json.loads(p.read_text(encoding='utf-8'));shutil.copy2(p,OUT/'data'/name)
    chart = ROOT / 'data/readme-progress.svg'
    if chart.exists(): shutil.copy2(chart, OUT / 'data/readme-progress.svg')
    learning = ROOT / 'data/learning'
    if (learning/'latest.json').exists():
        from learning_visuals import generate as learning_visuals
        learning_visuals(ROOT/'data')
        (OUT/'data/learning').mkdir()
        for name in ['latest.json','visuals.json','evolution.svg','pilot.svg']:
            if (learning/name).exists(): shutil.copy2(learning/name, OUT/'data/learning'/name)
    if (ROOT/'data/math-coverage/index.json').exists():
        (OUT/'data/math-coverage').mkdir()
        shutil.copy2(ROOT/'data/math-coverage/index.json', OUT/'data/math-coverage/index.json')
    coverage, _ = read_coverage(ROOT / 'data/coverage')
    shutil.copytree(ROOT / 'data/coverage', OUT / 'data/coverage',
                    ignore=shutil.ignore_patterns('.*', '*.tmp', 'retention.json'))
    articles={
      'RESEARCH':'docs/RESEARCH.md','REVIEW_RESPONSE':'docs/REVIEW_RESPONSE.md','CLUSTER':'docs/CLUSTER.md','PROTOCOL':'docs/PROTOCOL.md','ARCHIVE':'docs/ARCHIVE.md',
      'SEARCH_VERDICT':'research/archive/research-2026-09-09/SEARCH_VERDICT.md',
      'ALGORITHM_REVIEW':'research/archive/research-2026-09-09/ALGORITHM_REVIEW.md',
      'GEOMETRY_REVIEW':'research/archive/research-2026-09-09/GEOMETRY_REVIEW.md',
      'DISCOVERY_LEARNING':'research/archive/research-2026-09-09/DISCOVERY_LEARNING.md',
      'SHELL_PRUNING':'docs/SHELL_PRUNING.md','GEOMETRIC_POLICY':'docs/GEOMETRIC_POLICY.md','MATHEMATICAL_COVERAGE':'docs/MATHEMATICAL_COVERAGE.md','NATIVE_KERNEL':'docs/NATIVE_KERNEL.md','NEGATIVE_AUDITS':'docs/NEGATIVE_AUDITS.md',
      'DOMAIN_PROOF':'research/archive/phase3/DOMAIN_PROOF.md'}
    articles = {slug: rel for slug, rel in articles.items() if (ROOT / rel).exists()}
    rendered = render_research(articles)
    katex = ROOT / 'node_modules/katex'
    math_assets = OUT / 'assets/katex'
    math_assets.mkdir(parents=True)
    shutil.copy2(katex / 'dist/katex.min.css', math_assets / 'katex.min.css')
    shutil.copytree(katex / 'dist/fonts', math_assets / 'fonts')
    shutil.copy2(katex / 'LICENSE', math_assets / 'LICENSE.txt')
    for slug, rel in articles.items():
        article_path = 'research/' + slug.lower() + '/'
        dest = OUT / article_path
        dest.mkdir(parents=True, exist_ok=True)
        article = rendered[rel]
        content = (f'<article class="article research-document">'
                   f'<div class="research-tools"><a href="{BASE}research/">← The notebook</a>'
                   f'<a href="https://github.com/Kuberwastaken/math-gambling/blob/main/{rel}">Markdown source ↗</a></div>'
                   + article['html'] + '</article>')
        (dest / 'index.html').write_text(shell(article['title'] or slug.replace('_', ' ').title(),
                                               content, article_path, math=True), encoding='utf-8')
    downloads=OUT/'downloads';downloads.mkdir()
    local_files=['tools/runner.py','tools/search_core.py','tools/coverage_client.py','tools/coverage_format.py','tools/client_audit.py','data/runner-release.json','data/readme-progress.svg','data/strategy.json','data/site-config.json','docs/PROTOCOL.md','docs/RUNNER_SETUP.md','README.md','LICENSE']
    local_files += ['tools/native_kernel.py','tools/build_native.py','native/Cargo.toml','native/Cargo.lock','native/src/lib.rs','native/src/main.rs','docs/NATIVE_KERNEL.md','docs/NEGATIVE_AUDITS.md']
    local_files += ['data/coverage/' + name for name in referenced_files(ROOT/'data/coverage', coverage)]
    with zipfile.ZipFile(downloads/'math-gambling-runner.zip','w',zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(set(local_files)):
            # A tagged release must reproduce its ZIP despite checkout mtimes or host permissions.
            info = zipfile.ZipInfo('math-gambling/' + rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (ROOT / rel).read_bytes(), compresslevel=9)
    setup = ROOT/'docs/RUNNER_SETUP.md'
    if setup.exists(): shutil.copy2(setup, downloads/'RUNNER_SETUP.md')
    for p in (ROOT/'paper').glob('*.tex'):shutil.copy2(p,downloads/p.name)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in downloads.iterdir() if p.is_file()}
    (downloads/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2)+'\n', encoding='utf-8')
    (OUT/'404.html').write_text(shell('Page not found',f'<section class="article"><h1>This branch is empty.</h1><p>There is no page here. <a href="{BASE}">Return to the table.</a></p></section>'), encoding='utf-8')
    print(f'Built {len(list(OUT.rglob("*")))} entries in {OUT.relative_to(ROOT)}')
if __name__=='__main__':main()
