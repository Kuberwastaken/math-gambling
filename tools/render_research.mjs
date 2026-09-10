#!/usr/bin/env node
// Build-time Markdown and mathematics. Visitors need no rendering script or CDN.
import MarkdownIt from 'markdown-it';
import footnote from 'markdown-it-footnote';
import { katex } from '@mdit/plugin-katex';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const REPO = 'https://github.com/Kuberwastaken/math-gambling/blob/main/';

function sourceLink(href, source, published) {
  if (/^(?:https?:|mailto:|#)/i.test(href)) return href;
  if (href.startsWith('/math-gambling/')) return href;
  if (/^(?:[a-z][a-z0-9+.-]*:|\/\/|\/)/i.test(href)) {
    throw new Error(`Unsupported research link ${href} in ${source}`);
  }
  const match = /^([^?#]*)(\?[^#]*)?(#.*)?$/.exec(href);
  const rel = path.posix.normalize(path.posix.join(path.posix.dirname(source), decodeURIComponent(match[1])));
  if (rel.startsWith('../') || !existsSync(path.join(ROOT, rel))) {
    throw new Error(`Missing research source ${href} in ${source}`);
  }
  return (published[rel] ?? REPO + rel.split('/').map(encodeURIComponent).join('/')) +
    (match[2] ?? '') + (match[3] ?? '');
}

function headingText(inline) {
  return (inline.children ?? []).map(t => t.content).join('');
}

export function renderResearch(text, { source, published = {} }) {
  const md = new MarkdownIt({ html: false, linkify: true, typographer: false })
    .use(footnote)
    .use(katex, {
      delimiters: 'all',
      trust: false,
      throwOnError: true,
      maxExpand: 1000,
      maxSize: 20,
      output: 'htmlAndMathml',
      // LaTeX source line breaks are normal; other unsupported syntax fails below.
      logger: code => code === 'newLineInDisplayMode' ? 'ignore' : 'error',
    });
  const originalLink = md.renderer.rules.link_open;
  md.renderer.rules.link_open = (tokens, idx, options, env, renderer) => {
    const token = tokens[idx];
    token.attrSet('href', sourceLink(token.attrGet('href'), source, published));
    return originalLink ? originalLink(tokens, idx, options, env, renderer)
      : renderer.renderToken(tokens, idx, options);
  };
  const originalImage = md.renderer.rules.image;
  md.renderer.rules.image = (tokens, idx, options, env, renderer) => {
    const token = tokens[idx];
    token.attrSet('src', sourceLink(token.attrGet('src'), source, published));
    return originalImage(tokens, idx, options, env, renderer);
  };
  md.renderer.rules.table_open = () => '<div class="research-table" role="region" aria-label="Research comparison table" tabindex="0"><table>\n';
  md.renderer.rules.table_close = () => '</table></div>\n';

  const env = {};
  const tokens = md.parse(text, env);
  const headings = [];
  const used = new Map();
  let title = '';
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].type !== 'heading_open') continue;
    const label = headingText(tokens[i + 1]);
    const stem = label.toLowerCase().normalize('NFKD').replace(/[^\p{L}\p{N}\s-]/gu, '')
      .trim().replace(/\s+/g, '-') || 'section';
    const suffix = used.get(stem) ?? 0;
    used.set(stem, suffix + 1);
    const id = stem + (suffix ? `-${suffix}` : '');
    tokens[i].attrSet('id', id);
    if (tokens[i].tag === 'h1' && !title) title = label;
    if (tokens[i].tag === 'h2') headings.push({ id, label });
  }
  const rendered = md.renderer.render(tokens, md.options, env);
  if (/class=['"][^'"]*katex-error/.test(rendered)) {
    throw new Error(`Invalid mathematical notation in ${source}; fix it before publishing.`);
  }
  const toc = headings.length < 3 ? '' : '<details class="research-contents"><summary>On this page</summary><ol>' +
    headings.map(({ id, label }) => `<li><a href="#${md.utils.escapeHtml(id)}">${md.utils.escapeHtml(label)}</a></li>`).join('') +
    '</ol></details>';
  const body = rendered.replace(/(<h1\b[^>]*>[\s\S]*?<\/h1>)/, `$1\n${toc}`);
  return { title, html: body, headings };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { articles, published } = JSON.parse(readFileSync(0, 'utf8'));
  process.stdout.write(JSON.stringify(articles.map(article => ({
    ...renderResearch(article.text, { source: article.source, published }),
    source: article.source,
  }))));
}
