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

// --- Interaction checks -----------------------------------------------------
// These were previously a manual QA list. Anything a human had to click to
// confirm is worth a machine clicking on every push.

{
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`http://127.0.0.1:${PORT}/index.html`, { waitUntil: 'networkidle' });

  // Home links must actually resolve, not merely exist.
  const hrefs = await page.$$eval('a[href$=".html"], a[href^="benchmark"]', (as) =>
    [...new Set(as.map((a) => a.getAttribute('href')))]);
  for (const href of hrefs) {
    const response = await page.request.get(`http://127.0.0.1:${PORT}/${href.replace(/^\//, '')}`);
    check(response.ok(), `home link ${href} -> HTTP ${response.status()}`);
  }
  await page.close();
}

{
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`http://127.0.0.1:${PORT}/benchmarks.html`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(200);

  const total = await page.$$eval('.problem-card', (c) => c.length);
  check(total > 0, 'library renders no problem cards');

  // Search narrows the list. The term is taken from a card actually on the
  // page rather than hard-coded, so this checks the control rather than
  // asserting which problems happen to exist today.
  const firstTitle = await page.$eval('.problem-card h3', (el) => el.textContent.trim());
  const term = firstTitle.split(/\s+/)[0];
  await page.fill('[data-search]', term);
  await page.waitForTimeout(150);
  const searched = await page.$$eval('.problem-card', (c) => c.length);
  check(
    searched > 0 && searched < total,
    `search for "${term}" did not narrow the list (${searched}/${total})`,
  );

  // Category tabs filter.
  await page.fill('[data-search]', '');
  await page.waitForTimeout(100);
  const tabs = await page.$$('[data-category]');
  if (tabs.length > 1) {
    await tabs[1].click();
    await page.waitForTimeout(150);
    const filtered = await page.$$eval('.problem-card', (c) => c.length);
    check(filtered > 0 && filtered <= total, 'category filter returned nothing');
  }

  // Every benchmark the library links to must load.
  await tabs[0]?.click();
  await page.waitForTimeout(150);
  const links = await page.$$eval('.problem-card', (cards) =>
    cards.map((c) => c.getAttribute('href')));
  for (const href of links) {
    const response = await page.request.get(`http://127.0.0.1:${PORT}/${href}`);
    check(response.ok(), `benchmark ${href} -> HTTP ${response.status()}`);
  }
  await page.close();
}

{
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`http://127.0.0.1:${PORT}/benchmark.html?problem=support-ticket-routing`, {
    waitUntil: 'networkidle',
  });
  await page.click('[data-edit]');
  await page.waitForTimeout(150);

  const chips = () => page.textContent('[data-req-chips]');
  const table = () => page.textContent('[data-results-body]');

  // Sliders must change what the page states.
  const beforeAccuracy = await chips();
  await page.$eval('[data-accuracy]', (el) => {
    el.value = 99;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.waitForTimeout(150);
  check((await chips()) !== beforeAccuracy, 'accuracy slider did not update the page');

  // Volume must move the projected cost.
  const beforeCost = await page.textContent('[data-kpis]');
  await page.$eval('[data-volume]', (el) => {
    el.value = 1000000;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.waitForTimeout(150);
  check((await page.textContent('[data-kpis]')) !== beforeCost, 'volume did not change cost');

  // Auditability is an invariant rather than a diff: whenever it is required,
  // nothing non-auditable may be marked as meeting the requirements. Asserting
  // that the toggle *changes* the table would only hold while some measured
  // method is non-auditable, which is a property of today's data and not of
  // the control.
  await page.$eval('[data-accuracy]', (el) => {
    el.value = 1;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.$eval('[data-audit]', (el) => {
    el.checked = true;
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await page.waitForTimeout(200);
  const offenders = await page.$$eval('[data-results-body] tr', (rows) =>
    rows
      .filter((row) => {
        const cells = [...row.querySelectorAll('td')];
        const auditable = cells[5]?.textContent.includes('Yes');
        const passes = cells[6]?.textContent.includes('Pass');
        return passes && !auditable;
      })
      .map((row) => row.querySelector('strong')?.textContent),
  );
  check(
    offenders.length === 0,
    `auditability required, but these were marked passing anyway: ${offenders.join(', ')}`,
  );

  // An unrun method must never be marked as meeting anything: its stored
  // zeroes would otherwise read as instant and free at a low accuracy bar.
  const unrunPassing = await page.$$eval('[data-results-body] tr.unrun-row', (rows) =>
    rows.filter((row) => row.textContent.includes('Pass')).length,
  );
  check(unrunPassing === 0, 'an unrun method was marked as meeting the requirements');

  // The table lists every method in the comparison set, so the reader can see
  // what has not been run. The chart plots only methods that have figures —
  // an unrun method has none, and plotting its zeroes would plant a point at
  // the origin claiming a measurement nobody took. So the two agree on the
  // methods with results, and differ by exactly the unrun ones.
  const points = await page.$$eval('.data-point', (p) => p.length);
  const rows = await page.$$eval('[data-results-body] tr', (r) => r.length);
  const unrunRows = await page.$$eval('[data-results-body] tr.unrun-row', (r) => r.length);
  check(
    points === rows - unrunRows,
    `chart has ${points} points; table has ${rows} rows of which ${unrunRows} are unrun`,
  );
  check(unrunRows > 0, 'fixture no longer covers unrun methods, so this check is vacuous');

  // The chart's table fallback must be reachable and populated.
  await page.click('[data-view="table"]');
  await page.waitForTimeout(150);
  const fallbackRows = await page.$$eval('[data-chart-table] tbody tr', (r) => r.length);
  check(fallbackRows === rows, 'chart table fallback does not match the comparison table');
  await page.click('[data-view="chart"]');

  // Keyboard users must reach navigation, controls, and chart points.
  const reachable = await page.evaluate(() => {
    const focusable = [...document.querySelectorAll(
      'a[href], button, input, [tabindex="0"]',
    )].filter((el) => el.offsetParent !== null);
    return {
      nav: focusable.some((el) => el.closest('.sidebar')),
      controls: focusable.some((el) => el.matches('[data-accuracy], [data-edit]')),
      points: focusable.some((el) => el.classList.contains('data-point')),
    };
  });
  check(reachable.nav, 'keyboard cannot reach navigation');
  check(reachable.controls, 'keyboard cannot reach requirement controls');
  check(reachable.points, 'keyboard cannot reach chart points');
  await page.close();
}

// The evidence rule, exercised against the module the site actually ships.
const page = await browser.newPage();
await page.goto(`http://127.0.0.1:${PORT}/benchmark.html?problem=support-ticket-routing`, {
  waitUntil: 'networkidle',
});
const rule = await page.evaluate(async () => {
  const {
    getRecommendation, RECOMMENDATION_STATUS, countsAsEvidence,
    methodMeetsRequirements, hasNoResult,
  } = await import('./assets/app.js');
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
    notRunNotEvidence: countsAsEvidence(m('x', 1, 0, 'NOT_RUN')),
    notRunDetected: hasNoResult(m('x', 1, 0, 'NOT_RUN')),
    /* The dangerous case, which no slider can reach: an unrun method stores
       zeroes, so against a zero accuracy bar it reads as instant and free and
       would outrank every method that actually ran. */
    unrunNeverMeetsRequirements: methodMeetsRequirements(
      { ...m('x', 1, 0, 'NOT_RUN'), latencyMs: 0, costPer1k: 0 },
      { minAccuracy: 0, maxLatencyMs: 1000, auditabilityRequired: false, monthlyVolume: 1 },
    ),
    incomplete: RECOMMENDATION_STATUS.INCOMPLETE,
  };
});
await page.close();

check(rule.allMeasured === 'PASSING_METHOD_FOUND', 'fully measured set must recommend');
check(rule.mixed === rule.incomplete, 'mixed provenance must be BENCHMARK_INCOMPLETE');
check(rule.demoWinnerBlocked === null, 'a DEMO method must never win');
check(rule.demoNotEvidence === false, 'DEMO must not count as evidence');
check(rule.missingStateFailsClosed === false, 'missing provenance must fail closed');
check(rule.notRunNotEvidence === false, 'NOT_RUN must not count as evidence');
check(rule.notRunDetected === true, 'NOT_RUN must be recognised as having no result');
check(
  rule.unrunNeverMeetsRequirements === false,
  'an unrun method met the requirements — its zeroes were read as real figures',
);

await browser.close();
server.close();

if (failures.length) {
  console.error('FAILED:\n' + failures.map((f) => `  - ${f}`).join('\n'));
  process.exit(1);
}
console.log(
  `OK: ${PAGES.length} pages x 2 widths, interactions exercised, ` +
  'evidence rule verified in-browser',
);
