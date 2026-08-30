/**
 * Frontend gate for CI.
 *
 * Encodes the checks that were previously run by hand: every page renders
 * without console errors or failed requests, nothing overflows horizontally at
 * desktop or mobile width, and — most importantly — the evidence rule from
 * section 3.1 of PROJECT_STANDARD.md holds in the browser exactly as it does in
 * the backend. Exits non-zero on the first failure.
 */
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';

const ROOT = new URL('../frontend/', import.meta.url).pathname;
const PORT = 8411;
const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.svg': 'image/svg+xml', '.json': 'application/json',
};

const server = createServer(async (request, response) => {
  const path = normalize(decodeURIComponent(new URL(request.url, 'http://x').pathname));
  const file = join(ROOT, path === '/' ? 'index.html' : path);
  try {
    const body = await readFile(file);
    response.writeHead(200, { 'content-type': TYPES[extname(file)] ?? 'application/octet-stream' });
    response.end(body);
  } catch {
    response.writeHead(404).end('not found');
  }
});
await new Promise((resolve) => server.listen(PORT, resolve));

const failures = [];
const check = (condition, message) => { if (!condition) failures.push(message); };

// CI uses Playwright's own download; CHROMIUM_PATH lets a preinstalled
// browser be used instead (as in some dev sandboxes).
const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
);
const PAGES = [
  'index.html',
  'benchmarks.html',
  'methodology.html',
  'benchmark.html?problem=support-ticket-routing',
  'benchmark.html?problem=invoice-field-extraction',
];

for (const path of PAGES) {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const problems = [];
    page.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
    page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
    page.on('response', (r) => { if (r.status() >= 400) problems.push(`http ${r.status()} ${r.url()}`); });

    await page.goto(`http://127.0.0.1:${PORT}/${path}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(200);

    check(problems.length === 0, `${path} @${width}: ${problems.join('; ')}`);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    check(overflow <= 0, `${path} @${width}: ${overflow}px horizontal overflow`);
    await page.close();
  }
}

// The evidence rule, exercised against the module the site actually ships.
const page = await browser.newPage();
await page.goto(`http://127.0.0.1:${PORT}/benchmark.html?problem=support-ticket-routing`, {
  waitUntil: 'networkidle',
});
const rule = await page.evaluate(async () => {
  const { getRecommendation, RECOMMENDATION_STATUS, countsAsEvidence } =
    await import('./assets/app.js');
  const m = (id, rank, accuracy, resultState) => ({
    id, shortName: id, complexityRank: rank, accuracy, latencyMs: 10,
    costPer1k: 0.1, auditable: true, deterministic: true, kind: 'rules', resultState,
  });
  const req = { minAccuracy: 90, maxLatencyMs: 1000, auditabilityRequired: false, monthlyVolume: 1000 };
  return {
    allMeasured: getRecommendation(
      [m('a', 1, 95, 'MEASURED'), m('b', 2, 99, 'MEASURED')], req).status,
    mixed: getRecommendation(
      [m('a', 1, 95, 'MEASURED'), m('b', 2, 99, 'DEMO')], req).status,
    demoWinnerBlocked: getRecommendation(
      [m('demo', 1, 99.9, 'DEMO'), m('meas', 2, 95, 'MEASURED')], req).winner,
    demoNotEvidence: countsAsEvidence(m('x', 1, 99, 'DEMO')),
    missingStateFailsClosed: countsAsEvidence({ id: 'x', accuracy: 99 }),
    incomplete: RECOMMENDATION_STATUS.INCOMPLETE,
  };
});
await page.close();

check(rule.allMeasured === 'PASSING_METHOD_FOUND', 'fully measured set must recommend');
check(rule.mixed === rule.incomplete, 'mixed provenance must be BENCHMARK_INCOMPLETE');
check(rule.demoWinnerBlocked === null, 'a DEMO method must never win');
check(rule.demoNotEvidence === false, 'DEMO must not count as evidence');
check(rule.missingStateFailsClosed === false, 'missing provenance must fail closed');

await browser.close();
server.close();

if (failures.length) {
  console.error('FAILED:\n' + failures.map((f) => `  - ${f}`).join('\n'));
  process.exit(1);
}
console.log(`OK: ${PAGES.length} pages x 2 widths, evidence rule verified in-browser`);
