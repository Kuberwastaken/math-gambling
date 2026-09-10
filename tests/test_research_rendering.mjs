import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { renderResearch } from '../tools/render_research.mjs';

const source = 'docs/RESEARCH.md';

test('research uses semantic Markdown, linked footnotes, and real inline/display math', () => {
  const result = renderResearch(String.raw`# A readable paper

Inline \(x^3\) and $y^3$.

\[
\frac{4(114-z^3)-S^3}{3S}=V^2
\]

## Arithmetic

1. Generate a root.
2. Check it exactly.
   - Keep its proof.

| Method | Tests |
|---|---:|
| Exact | 114 |

An observation.[^source]

## Experiments

The second section.

## Experiments

The third section.

[^source]: A source with **emphasis**.
`, { source });
  assert.equal(result.title, 'A readable paper');
  assert.match(result.html, /<ol>\s*<li>/);
  assert.match(result.html, /<ul>\s*<li>Keep its proof/);
  assert.match(result.html, /<thead>/);
  assert.match(result.html, /<td[^>]*>114<\/td>/);
  assert.equal((result.html.match(/class="katex"/g) ?? []).length, 3);
  assert.match(result.html, /<math[^>]*display="block"/);
  assert.match(result.html, /href="#fn1" id="fnref1"/);
  assert.match(result.html, /id="fn1"/);
  assert.match(result.html, /href="#fnref1"/);
  assert.match(result.html, /<details class="research-contents">/);
  assert.match(result.html, /id="experiments-1"/);
});

test('research escapes HTML and preserves literal math in code', () => {
  const rendered = renderResearch(String.raw`# Safe source

<script>alert(1)</script>

[bad](javascript:alert(1))

${'`'}\(not math\)${'`'}

~~~text
\[literal block\]
$literal dollars$
~~~
`, { source }).html;
  assert.doesNotMatch(rendered, /<script|href="javascript:|class="katex"/);
  assert.match(rendered, /&lt;script&gt;/);
  assert.match(rendered, /<code>\\\(not math\\\)<\/code>/);
  assert.match(rendered, /\$literal dollars\$/);
});

test('local research references resolve to published pages or existing repository evidence', () => {
  const rendered = renderResearch('[Archive](ARCHIVE.md) [Evidence](../research/archive/ARCHIVE_MANIFEST.json)', {
    source,
    published: { 'docs/ARCHIVE.md': '/math-gambling/research/archive/' },
  }).html;
  assert.match(rendered, /href="\/math-gambling\/research\/archive\/"/);
  assert.match(rendered, /href="https:\/\/github.com\/Kuberwastaken\/math-gambling\/blob\/main\/research\/archive\/ARCHIVE_MANIFEST.json"/);
  assert.throws(() => renderResearch('[Missing](does-not-exist.md)', { source }), /Missing research source/);
  assert.throws(() => renderResearch('[Outside](../../../../etc/passwd)', { source }), /Missing research source/);
});

test('the cited search verdict renders every equation and all 21 footnotes without losing its tables', () => {
  const source = 'research/archive/research-2026-09-09/SEARCH_VERDICT.md';
  const text = readFileSync(new URL('../' + source, import.meta.url), 'utf8');
  const rendered = renderResearch(text, {
    source,
    published: {
      'research/archive/phase3/DOMAIN_PROOF.md': '/math-gambling/research/domain_proof/',
      'research/archive/research-2026-09-09/ALGORITHM_REVIEW.md': '/math-gambling/research/algorithm_review/',
      'research/archive/research-2026-09-09/DISCOVERY_LEARNING.md': '/math-gambling/research/discovery_learning/',
      'research/archive/research-2026-09-09/GEOMETRY_REVIEW.md': '/math-gambling/research/geometry_review/',
    },
  }).html;
  const equations = (text.match(/\\\(/g) ?? []).length + (text.match(/\\\[/g) ?? []).length;
  assert.equal((rendered.match(/class="katex"/g) ?? []).length, equations);
  assert.equal((rendered.match(/class="footnote-item"/g) ?? []).length, 21);
  assert.equal((rendered.match(/<table>/g) ?? []).length, 2);
  assert.equal((rendered.match(/<h1\b/g) ?? []).length, 1);
  assert.match(rendered, /href="\/math-gambling\/research\/domain_proof\/"/);
  assert.doesNotMatch(rendered, /katex-error|\[\^\d+\]/);
});
