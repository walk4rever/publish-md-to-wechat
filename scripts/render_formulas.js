#!/usr/bin/env node
// Batch-renders LaTeX formulas to inline SVG via MathJax, used by
// wechat_publisher.py to embed math directly in article HTML instead of
// linking to an external image-rendering service. Reads a JSON array of
// {id, latex, display} from stdin, writes {id: {ok, svg|error}} to stdout.
'use strict';

const { mathjax } = require('mathjax-full/js/mathjax.js');
const { TeX } = require('mathjax-full/js/input/tex.js');
const { SVG } = require('mathjax-full/js/output/svg.js');
const { liteAdaptor } = require('mathjax-full/js/adaptors/liteAdaptor.js');
const { RegisterHTMLHandler } = require('mathjax-full/js/handlers/html.js');
const { AllPackages } = require('mathjax-full/js/input/tex/AllPackages.js');

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

async function main() {
  const raw = await readStdin();
  const items = JSON.parse(raw);

  const adaptor = liteAdaptor();
  RegisterHTMLHandler(adaptor);
  const tex = new TeX({ packages: AllPackages });
  const svg = new SVG({ fontCache: 'none' });
  const doc = mathjax.document('', { InputJax: tex, OutputJax: svg });

  const results = {};
  for (const item of items) {
    try {
      const node = doc.convert(item.latex, { display: !!item.display });
      const outerHtml = adaptor.outerHTML(node);
      // Invalid LaTeX doesn't throw — MathJax embeds a visible red "error"
      // SVG (a <merror> node with data-mjx-error) instead of failing. Treat
      // that as a failure too, so the caller falls back rather than
      // publishing a red error box into the article.
      const errorMatch = outerHtml.match(/data-mjx-error="([^"]*)"/);
      if (errorMatch) throw new Error(`MathJax error: ${errorMatch[1]}`);
      const match = outerHtml.match(/<svg[\s\S]*<\/svg>/);
      if (!match) throw new Error('MathJax produced no <svg> output');
      results[item.id] = { ok: true, svg: match[0] };
    } catch (e) {
      results[item.id] = { ok: false, error: String((e && e.message) || e) };
    }
  }

  process.stdout.write(JSON.stringify(results));
}

main().catch((e) => {
  process.stderr.write(String((e && e.stack) || e) + '\n');
  process.exit(1);
});
