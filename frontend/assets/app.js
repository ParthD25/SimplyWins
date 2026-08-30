import { benchmarkProblems, getProblem } from './data.js';

export function methodMeetsRequirements(method, requirements) {
  return method.accuracy >= requirements.minAccuracy &&
    method.latencyMs <= requirements.maxLatencyMs &&
    (!requirements.auditabilityRequired || method.auditable);
}

/* Only MEASURED figures may shape an outcome — section 3.1 of
   PROJECT_STANDARD.md. Anything else is display-only. Defaults to DEMO so the
   rule fails closed when provenance is missing. */
export function countsAsEvidence(method) {
  return (method.resultState ?? 'DEMO') === 'MEASURED';
}

export const RECOMMENDATION_STATUS = {
  PASSING: 'PASSING_METHOD_FOUND',
  NO_PASSING: 'NO_PASSING_METHOD',
  INCOMPLETE: 'BENCHMARK_INCOMPLETE',
};

/* Mirrors the backend rule. Three outcomes, two of which name no winner:
   an unmeasured method could still displace the current leader, so while any
   method is unmeasured the answer is BENCHMARK_INCOMPLETE rather than a pick. */
export function getRecommendation(methods, requirements) {
  const measured = methods.filter(countsAsEvidence);
  const measuredCount = measured.length;
  const methodCount = methods.length;

  const ranked = measured
    .filter((method) => methodMeetsRequirements(method, requirements))
    .sort((a, b) =>
      a.complexityRank - b.complexityRank ||
      a.costPer1k - b.costPer1k ||
      a.latencyMs - b.latencyMs ||
      a.id.localeCompare(b.id));

  const bestMeasured = ranked[0] ?? null;
  const base = { passing: ranked, bestMeasured, measuredCount, methodCount };

  if (measuredCount < methodCount) {
    return {
      ...base,
      status: RECOMMENDATION_STATUS.INCOMPLETE,
      winner: null,
      reason: `Benchmark incomplete: ${measuredCount} of ${methodCount} methods measured. No recommendation is made until every method has been measured, because an unmeasured method could change the outcome.`,
    };
  }

  if (!ranked.length) {
    return {
      ...base,
      status: RECOMMENDATION_STATUS.NO_PASSING,
      winner: null,
      reason: 'No method clears every active requirement. No winner is nominated.',
    };
  }

  return {
    ...base,
    status: RECOMMENDATION_STATUS.PASSING,
    winner: bestMeasured,
    reason: `${bestMeasured.shortName} is the lowest-complexity approach that clears every active requirement.`,
  };
}

export function setupMobileNav() {
  const toggle = document.querySelector('[data-nav-toggle]');
  const sidebar = document.querySelector('.sidebar');
  const scrim = document.querySelector('.sidebar-scrim');
  if (!toggle || !sidebar || !scrim) return;
  const close = () => { sidebar.classList.remove('sidebar-open'); scrim.hidden = true; };
  toggle.addEventListener('click', () => {
    sidebar.classList.toggle('sidebar-open');
    scrim.hidden = !sidebar.classList.contains('sidebar-open');
  });
  scrim.addEventListener('click', close);
  sidebar.querySelectorAll('a').forEach((link) => link.addEventListener('click', close));
}

function problemIcon(category) {
  const icons = {
    'Document Processing': '▤',
    'Classification': '◇',
    'Data Matching': '⇄',
    'Text Understanding': '¶',
  };
  return icons[category] ?? '•';
}

export function renderProblemCards(container, problems = benchmarkProblems) {
  container.innerHTML = problems.map((problem) => {
    const recommendation = getRecommendation(problem.results, problem.requirements);
    return `<a class="problem-card" href="benchmark.html?problem=${problem.slug}">
      <div class="problem-card-top"><span class="category-icon">${problemIcon(problem.category)}</span><span class="status-chip status-demo">Demo results</span></div>
      <div><div class="problem-category">${problem.category}</div><h3>${problem.title}</h3><p>${problem.description}</p></div>
      <div class="problem-card-bottom">${recommendation.winner
        ? `<span>Recommended: <strong>${recommendation.winner.shortName}</strong></span>`
        : `<span class="card-incomplete">${recommendation.measuredCount} of ${recommendation.methodCount} measured</span>`}<span aria-hidden="true">↗</span></div>
    </a>`;
  }).join('');
}

export function setupLibrary() {
  const grid = document.querySelector('[data-problem-grid]');
  const input = document.querySelector('[data-search]');
  const tabs = [...document.querySelectorAll('[data-category]')];
  if (!grid || !input) return;
  // A ?category= link (from the benchmark page rail) preselects that filter.
  const requested = new URLSearchParams(location.search).get('category');
  const known = [...new Set(benchmarkProblems.map((problem) => problem.category))];
  let category = known.includes(requested) ? requested : 'All';
  const update = () => {
    const query = input.value.toLowerCase().trim();
    const filtered = benchmarkProblems.filter((problem) => (category === 'All' || problem.category === category) && (!query || `${problem.title} ${problem.description} ${problem.category}`.toLowerCase().includes(query)));
    renderProblemCards(grid, filtered);
    const count = document.querySelector('[data-result-count]');
    if (count) count.textContent = filtered.length;
  };
  tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.category === category));
  input.addEventListener('input', update);
  tabs.forEach((tab) => tab.addEventListener('click', () => {
    category = tab.dataset.category;
    tabs.forEach((item) => item.classList.toggle('active', item === tab));
    update();
  }));
  update();
}

function logScale(value, min, max) {
  const safe = Math.max(value, min);
  return (Math.log10(safe) - Math.log10(min)) / (Math.log10(max) - Math.log10(min));
}

const METHOD_COLORS = {
  'rules': '#15966b',
  'traditional-ml': '#2457f5',
  'small-model': '#7756d8',
  'frontier-llm': '#e24a4a',
};

/* Sub-cent costs are real for local methods, so a flat two decimals would
   print "$0.00" for a figure that is not zero. */
const money = (value) => {
  if (value === 0) return '$0.00';
  if (value < 0.01) return `$${value.toPrecision(2)}`;
  return `$${value.toFixed(2)}`;
};

/* Measured local methods run in fractions of a millisecond; rounding those to
   an integer would display a real 0.11ms as "0ms". */
const formatLatency = (ms) =>
  (ms < 10 ? `${Number(ms.toFixed(2))}ms` : `${Math.round(ms)}ms`);
const compact = (value) => Intl.NumberFormat('en-US', { notation: 'compact' }).format(value);
const monthlyCost = (method, requirements) => method.costPer1k * (requirements.monthlyVolume / 1000);

/* The scatter is the primary evidence view. It stays compact so the table
   below it remains visible without scrolling on a laptop. */
function renderScatter(problem, requirements, recommendation) {
  const host = document.querySelector('[data-scatter]');
  if (!host) return;
  const W = 660, H = 300, m = { top: 18, right: 20, bottom: 48, left: 52 };
  const pw = W - m.left - m.right;
  const ph = H - m.top - m.bottom;

  const costs = problem.results.map((r) => r.costPer1k);
  const minCost = 0.01;
  const maxCost = Math.max(...costs, 10) * 2.2;
  // Floor the accuracy axis to a round number below the lowest value on show,
  // so points never sit on the frame.
  const lowest = Math.min(...problem.results.map((r) => r.accuracy), requirements.minAccuracy) - 3;
  // Pick a tick step that lands on whole numbers, then floor the axis to it,
  // so labels read 90/92/94 rather than 90/92.5/95.
  const span = 100 - lowest;
  const step = span <= 12 ? 2 : span <= 30 ? 5 : 10;
  const minAcc = Math.max(0, Math.floor(lowest / step) * step);
  const x = (cost) => m.left + logScale(cost, minCost, maxCost) * pw;
  const y = (accuracy) => m.top + (1 - (accuracy - minAcc) / (100 - minAcc)) * ph;

  const yTicks = [];
  for (let tick = minAcc; tick <= 100 + 1e-9; tick += step) yTicks.push(tick);
  const xTicks = [0.01, 0.1, 1, 10, 100].filter((tick) => tick <= maxCost);
  const thresholdY = y(requirements.minAccuracy);

  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Accuracy against cost per 1,000 tasks for each method. The same data is available in the Table view.">
    ${yTicks.map((t) => `<line x1="${m.left}" x2="${W - m.right}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" class="grid-line"/><text x="${m.left - 10}" y="${(y(t) + 4).toFixed(1)}" text-anchor="end" class="axis-label">${t.toFixed(0)}</text>`).join('')}
    ${xTicks.map((t) => `<line y1="${m.top}" y2="${H - m.bottom}" x1="${x(t).toFixed(1)}" x2="${x(t).toFixed(1)}" class="grid-line vertical"/><text x="${x(t).toFixed(1)}" y="${H - m.bottom + 20}" text-anchor="middle" class="axis-label">$${t < 1 ? t.toFixed(2) : t.toFixed(2)}</text>`).join('')}
    <line x1="${m.left}" x2="${W - m.right}" y1="${thresholdY.toFixed(1)}" y2="${thresholdY.toFixed(1)}" class="threshold-line"/>
    <text x="${m.left + 6}" y="${(thresholdY - 7).toFixed(1)}" class="threshold-label">${requirements.minAccuracy}% requirement</text>
    ${problem.results.map((method) => {
      const passes = methodMeetsRequirements(method, requirements);
      const evidence = countsAsEvidence(method);
      const isWinner = recommendation.winner && method.id === recommendation.winner.id;
      const cx = x(method.costPer1k).toFixed(1);
      const cy = y(method.accuracy).toFixed(1);
      const ring = isWinner ? `<circle cx="${cx}" cy="${cy}" r="13" fill="none" stroke="#15966b" stroke-width="2"/>` : '';
      return `${ring}<circle class="data-point" tabindex="0" role="img" data-method="${method.id}" cx="${cx}" cy="${cy}" r="7" fill="${evidence ? METHOD_COLORS[method.kind] : '#fff'}" stroke="${evidence ? '#fff' : METHOD_COLORS[method.kind]}" stroke-width="2.5" stroke-dasharray="${evidence ? '' : '3 2'}" opacity="${evidence ? (passes ? 1 : 0.55) : 0.5}"><title>${method.name}: ${method.accuracy.toFixed(1)}% accuracy, ${money(method.costPer1k)} per 1K, ${formatLatency(method.latencyMs)}. ${passes ? 'Meets requirements' : 'Does not meet requirements'}. ${evidence ? 'Measured result.' : 'Illustrative only — excluded from the recommendation.'}</title></circle>`;
    }).join('')}
    <text x="${m.left + pw / 2}" y="${H - 8}" text-anchor="middle" class="axis-title">Cost per 1K tasks (USD, log scale)</text>
    <text x="14" y="${m.top + ph / 2}" text-anchor="middle" class="axis-title" transform="rotate(-90 14 ${m.top + ph / 2})">Accuracy (%)</text>
  </svg>`;
}

/* Legend doubles as a compact per-method readout, and names the recommendation
   so the chart is readable without cross-referencing the table. */
function renderChartLegend(problem, requirements, recommendation) {
  const host = document.querySelector('[data-chart-legend]');
  if (!host) return;
  host.innerHTML = [...problem.results].sort((a, b) => a.complexityRank - b.complexityRank).map((method) => {
    const isWinner = recommendation.winner && method.id === recommendation.winner.id;
    const evidence = countsAsEvidence(method);
    const marker = evidence
      ? `background:${METHOD_COLORS[method.kind]}`
      : `background:#fff;box-shadow:inset 0 0 0 2px ${METHOD_COLORS[method.kind]}`;
    return `<span class="${evidence ? '' : 'legend-demo'}"><i style="${marker}"></i><b>${method.shortName}${isWinner ? '<em>Recommended</em>' : ''}${evidence ? '' : '<em class="legend-note">Illustrative</em>'}</b></span>`;
  }).join('');
}

/* Table fallback for the chart — required by the project standard, and the
   view a keyboard or screen-reader user is most likely to want. */
function renderChartTable(problem, requirements) {
  const host = document.querySelector('[data-chart-table]');
  if (!host) return;
  host.innerHTML = `<table class="results-table"><caption class="sr-only">Chart data in table form</caption>
    <thead><tr><th>Method</th><th>Evidence</th><th>Accuracy</th><th>Cost / 1K</th><th>Median latency</th><th>Meets requirements</th></tr></thead>
    <tbody>${[...problem.results].sort((a, b) => a.complexityRank - b.complexityRank).map((method) => {
      const passes = methodMeetsRequirements(method, requirements);
      const evidence = countsAsEvidence(method);
      return `<tr class="${evidence ? '' : 'demo-row'}"><td><span class="method-badge method-${method.kind}">${method.shortName}</span></td>
        <td><span class="state-tag state-${evidence ? 'measured' : 'demo'}">${evidence ? 'Measured' : 'Illustrative'}</span></td>
        <td>${method.accuracy.toFixed(1)}%</td><td>${money(method.costPer1k)}</td><td>${formatLatency(method.latencyMs)}</td>
        <td class="${passes ? 'pass-label' : 'fail-label'}">${passes ? '✓ Pass' : '× No'}</td></tr>`;
    }).join('')}</tbody></table>`;
}

function renderKpis(problem, requirements, recommendation) {
  const host = document.querySelector('[data-kpis]');
  if (!host) return;
  const { winner, bestMeasured, status, measuredCount, methodCount } = recommendation;
  const complete = status === RECOMMENDATION_STATUS.PASSING;

  // With no winner the derived metrics are left blank rather than borrowed from
  // a method that has not earned them.
  const value = (render) => (complete ? render(winner) : '—');

  const leadCard = complete
    ? `<div class="kpi kpi-lead"><span>Recommended</span><strong>${winner.shortName}</strong></div>`
    : status === RECOMMENDATION_STATUS.INCOMPLETE
      ? `<div class="kpi kpi-lead kpi-incomplete"><span>Benchmark incomplete</span><strong>${measuredCount} of ${methodCount} measured</strong>${bestMeasured ? `<small>Best measured so far: ${bestMeasured.shortName} — not a recommendation</small>` : '<small>No measured method clears the requirements yet</small>'}</div>`
      : `<div class="kpi kpi-lead kpi-none"><span>Recommendation</span><strong>No passing method</strong></div>`;

  host.innerHTML = `
    ${leadCard}
    <div class="kpi"><span>Meets Requirements</span><strong class="${complete ? 'kpi-yes' : 'kpi-no'}">${complete ? '✓ Yes' : '—'}</strong></div>
    <div class="kpi"><span>Accuracy (Best)</span><strong>${value((w) => `${w.accuracy.toFixed(1)}%`)}</strong></div>
    <div class="kpi"><span>Est. Monthly Cost</span><strong>${value((w) => money(monthlyCost(w, requirements)))}</strong><small>at ${compact(requirements.monthlyVolume)} / month</small></div>
    <div class="kpi"><span>Est. Latency (Best)</span><strong>${value((w) => `${formatLatency(w.latencyMs)}`)}</strong></div>`;
}

/* States the evidence position before any numbers are read. Section 3.1
   requires incompleteness to be visible, not merely implied. */
function renderEvidenceBanner(recommendation) {
  const host = document.querySelector('[data-evidence-banner]');
  if (!host) return;
  if (recommendation.status !== RECOMMENDATION_STATUS.INCOMPLETE) {
    host.hidden = true;
    return;
  }
  const { measuredCount, methodCount, bestMeasured } = recommendation;
  host.hidden = false;
  host.innerHTML = `<strong>Benchmark incomplete — ${measuredCount} of ${methodCount} methods measured.</strong>
    <p>Illustrative figures are shown for context but are excluded from the ranking, the chart's frontier, and any recommendation. No winner is named until every method has been measured, because an unmeasured method could change the outcome.${bestMeasured ? ` Best measured result so far is <b>${bestMeasured.shortName}</b>, which is not a recommendation.` : ''}</p>`;
}

function renderRequirementChips(requirements) {
  const host = document.querySelector('[data-req-chips]');
  if (!host) return;
  host.innerHTML = `
    <span class="req-chip">Accuracy ≥<strong>${requirements.minAccuracy}%</strong></span>
    <span class="req-chip">Max latency ≤<strong>${formatLatency(requirements.maxLatencyMs)}</strong></span>
    <span class="req-chip${requirements.auditabilityRequired ? '' : ' off'}">Auditability<strong>${requirements.auditabilityRequired ? 'Required' : 'Not required'}</strong></span>
    <span class="req-chip">Volume<strong>${compact(requirements.monthlyVolume)} / month</strong></span>`;
}

function renderTable(problem, requirements, recommendation) {
  const body = document.querySelector('[data-results-body]');
  if (!body) return;
  body.innerHTML = [...problem.results].sort((a, b) => a.complexityRank - b.complexityRank).map((method) => {
    const passes = methodMeetsRequirements(method, requirements);
    const isWinner = recommendation.winner && method.id === recommendation.winner.id;
    const evidence = countsAsEvidence(method);
    const rowClass = [isWinner ? 'winner-row' : '', evidence ? '' : 'demo-row'].filter(Boolean).join(' ');
    return `<tr class="${rowClass}">
      <td><div class="method-cell"><span class="method-badge method-${method.kind}">${method.shortName}</span><div><strong>${method.name}</strong><small>${method.notes}</small></div></div></td>
      <td><span class="state-tag state-${evidence ? 'measured' : 'demo'}">${evidence ? 'Measured' : 'Illustrative'}</span></td>
      <td>${method.accuracy.toFixed(1)}%</td><td>${money(method.costPer1k)}</td><td>${formatLatency(method.latencyMs)}</td>
      <td class="${method.auditable ? 'pass-label' : 'fail-label'}">${method.auditable ? '✓ Yes' : '× No'}</td>
      <td class="${passes ? 'pass-label' : 'fail-label'}">${passes ? '✓ Pass' : '× No'}</td>
    </tr>`;
  }).join('');
}

/* Right rail. Counts and picks are derived from the data, never hard-coded —
   the project standard forbids displaying invented metrics. */
function renderRail(problem) {
  const categories = document.querySelector('[data-categories]');
  if (categories) {
    const counts = new Map();
    benchmarkProblems.forEach((entry) => counts.set(entry.category, (counts.get(entry.category) ?? 0) + 1));
    categories.innerHTML = [...counts.entries()].map(([category, count]) => `
      <a class="rail-item" href="benchmarks.html?category=${encodeURIComponent(category)}">
        <span class="rail-icon" aria-hidden="true">${problemIcon(category)}</span>
        <div><strong>${category}</strong><small>${count} problem${count === 1 ? '' : 's'}</small></div>
      </a>`).join('');
  }

  const picks = document.querySelector('[data-top-picks]');
  if (picks) {
    picks.innerHTML = benchmarkProblems
      .filter((entry) => entry.slug !== problem.slug)
      .slice(0, 3)
      .map((entry) => {
        const pick = getRecommendation(entry.results, entry.requirements);
        const detail = pick.winner
          ? `→ <span class="rail-pick">${pick.winner.shortName}</span>`
          : `<span class="rail-incomplete">${pick.measuredCount} of ${pick.methodCount} measured</span>`;
        return `<a class="rail-item" href="benchmark.html?problem=${entry.slug}">
          <span class="rail-icon" aria-hidden="true">${problemIcon(entry.category)}</span>
          <div><strong>${entry.title}</strong><small>${detail}</small></div>
        </a>`;
      }).join('');
  }
}

export function setupBenchmarkPage() {
  const params = new URLSearchParams(location.search);
  const problem = getProblem(params.get('problem') || 'invoice-field-extraction');
  let requirements = structuredClone(problem.requirements);

  document.title = `${problem.title} — SimplestWins`;
  const text = {
    title: problem.title,
    category: problem.category,
    description: problem.description,
    question: problem.decisionQuestion,
    dataset: problem.datasetLabel,
    datasetSize: problem.datasetSize,
    rationale: problem.rationale,
  };
  Object.entries(text).forEach(([key, value]) => {
    document.querySelectorAll(`[data-${key}]`).forEach((el) => { el.textContent = value; });
  });

  const accuracy = document.querySelector('[data-accuracy]');
  const latency = document.querySelector('[data-latency]');
  const volume = document.querySelector('[data-volume]');
  const audit = document.querySelector('[data-audit]');

  const setControls = () => {
    accuracy.value = requirements.minAccuracy;
    latency.value = requirements.maxLatencyMs;
    volume.value = requirements.monthlyVolume;
    audit.checked = requirements.auditabilityRequired;
    document.querySelector('[data-accuracy-value]').textContent = `${requirements.minAccuracy}%`;
    document.querySelector('[data-latency-value]').textContent = `${formatLatency(requirements.maxLatencyMs)}`;
    document.querySelector('[data-volume-value]').textContent = compact(requirements.monthlyVolume);
  };

  const render = () => {
    setControls();
    renderRequirementChips(requirements);
    const recommendation = getRecommendation(problem.results, requirements);
    renderEvidenceBanner(recommendation);
    renderKpis(problem, requirements, recommendation);
    renderScatter(problem, requirements, recommendation);
    renderChartLegend(problem, requirements, recommendation);
    renderChartTable(problem, requirements);
    renderTable(problem, requirements, recommendation);
  };

  accuracy.addEventListener('input', () => { requirements.minAccuracy = Number(accuracy.value); render(); });
  latency.addEventListener('input', () => { requirements.maxLatencyMs = Number(latency.value); render(); });
  volume.addEventListener('input', () => { requirements.monthlyVolume = Number(volume.value); render(); });
  audit.addEventListener('change', () => { requirements.auditabilityRequired = audit.checked; render(); });
  document.querySelector('[data-reset]').addEventListener('click', () => {
    requirements = structuredClone(problem.requirements);
    render();
  });

  const editor = document.querySelector('#req-editor');
  const editButton = document.querySelector('[data-edit]');
  const toggleEditor = (open) => {
    editor.hidden = !open;
    editButton.setAttribute('aria-expanded', String(open));
    if (open) accuracy.focus();
  };
  editButton.addEventListener('click', () => toggleEditor(editor.hidden));
  document.querySelector('[data-close-edit]').addEventListener('click', () => { toggleEditor(false); editButton.focus(); });

  const chartView = document.querySelector('[data-chart-view]');
  const chartTable = document.querySelector('[data-chart-table]');
  document.querySelectorAll('[data-view]').forEach((button) => {
    button.addEventListener('click', () => {
      const wantsChart = button.dataset.view === 'chart';
      chartView.hidden = !wantsChart;
      chartTable.hidden = wantsChart;
      document.querySelectorAll('[data-view]').forEach((other) => {
        other.setAttribute('aria-pressed', String(other === button));
      });
    });
  });

  const share = document.querySelector('[data-share]');
  share.addEventListener('click', async () => {
    const original = share.lastChild.textContent;
    try {
      await navigator.clipboard.writeText(location.href);
      share.lastChild.textContent = 'Link copied';
    } catch {
      share.lastChild.textContent = 'Copy failed';
    }
    setTimeout(() => { share.lastChild.textContent = original; }, 1800);
  });

  // The runner does not exist yet. The button says so rather than pretending.
  const run = document.querySelector('[data-run]');
  const runNote = document.createElement('p');
  runNote.className = 'rail-note';
  runNote.style.cssText = 'margin:8px 0 0;color:#985f13';
  runNote.setAttribute('role', 'status');
  run.closest('.topbar').after(runNote);
  run.addEventListener('click', () => {
    runNote.textContent = 'No benchmark runner yet — every figure on this page is demo data. Measured runs arrive with the Python runner (Phase 3).';
  });

  renderRail(problem);
  render();
}

export { benchmarkProblems };
