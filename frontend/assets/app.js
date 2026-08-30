import { benchmarkProblems, getProblem } from './data.js';

export function methodMeetsRequirements(method, requirements) {
  return method.accuracy >= requirements.minAccuracy &&
    method.latencyMs <= requirements.maxLatencyMs &&
    (!requirements.auditabilityRequired || method.auditable);
}

export function getRecommendation(methods, requirements) {
  const passing = methods
    .filter((method) => methodMeetsRequirements(method, requirements))
    .sort((a, b) => a.complexityRank - b.complexityRank || a.costPer1k - b.costPer1k);

  if (passing.length) {
    return { winner: passing[0], passing, fallbackUsed: false, reason: `${passing[0].shortName} is the lowest-complexity approach that clears every active requirement.` };
  }

  const sorted = [...methods].sort((a, b) => {
    const score = (m) => m.accuracy - Math.log10(m.costPer1k + 1) * 2 - Math.max(0, m.latencyMs - requirements.maxLatencyMs) / 1000;
    return score(b) - score(a);
  });
  return { winner: sorted[0], passing: [], fallbackUsed: true, reason: `No method clears every active requirement. ${sorted[0].shortName} is the closest current option.` };
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
      <div class="problem-card-bottom"><span>Current pick: <strong>${recommendation.winner.shortName}</strong></span><span aria-hidden="true">↗</span></div>
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

const money = (value) => `$${value.toFixed(2)}`;
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
      const isWinner = recommendation.winner && method.id === recommendation.winner.id && !recommendation.fallbackUsed;
      const cx = x(method.costPer1k).toFixed(1);
      const cy = y(method.accuracy).toFixed(1);
      const ring = isWinner ? `<circle cx="${cx}" cy="${cy}" r="13" fill="none" stroke="#15966b" stroke-width="2"/>` : '';
      return `${ring}<circle class="data-point" tabindex="0" role="img" data-method="${method.id}" cx="${cx}" cy="${cy}" r="7" fill="${METHOD_COLORS[method.kind]}" stroke="#fff" stroke-width="2.5" opacity="${passes ? 1 : 0.55}"><title>${method.name}: ${method.accuracy.toFixed(1)}% accuracy, ${money(method.costPer1k)} per 1K, ${method.latencyMs}ms. ${passes ? 'Meets requirements' : 'Does not meet requirements'}.</title></circle>`;
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
    const isWinner = recommendation.winner && method.id === recommendation.winner.id && !recommendation.fallbackUsed;
    return `<span><i style="background:${METHOD_COLORS[method.kind]}"></i><b>${method.shortName}${isWinner ? '<em>Recommended</em>' : ''}</b></span>`;
  }).join('');
}

/* Table fallback for the chart — required by the project standard, and the
   view a keyboard or screen-reader user is most likely to want. */
function renderChartTable(problem, requirements) {
  const host = document.querySelector('[data-chart-table]');
  if (!host) return;
  host.innerHTML = `<table class="results-table"><caption class="sr-only">Chart data in table form</caption>
    <thead><tr><th>Method</th><th>Accuracy</th><th>Cost / 1K</th><th>Median latency</th><th>Meets requirements</th></tr></thead>
    <tbody>${[...problem.results].sort((a, b) => a.complexityRank - b.complexityRank).map((method) => {
      const passes = methodMeetsRequirements(method, requirements);
      return `<tr><td><span class="method-badge method-${method.kind}">${method.shortName}</span></td>
        <td>${method.accuracy.toFixed(1)}%</td><td>${money(method.costPer1k)}</td><td>${method.latencyMs}ms</td>
        <td class="${passes ? 'pass-label' : 'fail-label'}">${passes ? '✓ Pass' : '× No'}</td></tr>`;
    }).join('')}</tbody></table>`;
}

function renderKpis(problem, requirements, recommendation) {
  const host = document.querySelector('[data-kpis]');
  if (!host) return;
  const passed = !recommendation.fallbackUsed;
  const winner = recommendation.winner;

  // With no passing method there is no recommendation, so the derived metrics
  // are left blank rather than borrowed from a method that failed.
  const value = (render) => (passed ? render(winner) : '—');
  host.innerHTML = `
    <div class="kpi kpi-lead${passed ? '' : ' kpi-none'}">
      <span>${passed ? 'Best Recommendation' : 'Recommendation'}</span>
      <strong>${passed ? winner.shortName : 'No passing method'}</strong>
    </div>
    <div class="kpi"><span>Meets Requirements</span><strong class="${passed ? 'kpi-yes' : 'kpi-no'}">${passed ? '✓ Yes' : '× No'}</strong></div>
    <div class="kpi"><span>Accuracy (Best)</span><strong>${value((w) => `${w.accuracy.toFixed(1)}%`)}</strong></div>
    <div class="kpi"><span>Est. Monthly Cost</span><strong>${value((w) => money(monthlyCost(w, requirements)))}</strong><small>at ${compact(requirements.monthlyVolume)} / month</small></div>
    <div class="kpi"><span>Est. Latency (Best)</span><strong>${value((w) => `${w.latencyMs}ms`)}</strong></div>`;
}

function renderRequirementChips(requirements) {
  const host = document.querySelector('[data-req-chips]');
  if (!host) return;
  host.innerHTML = `
    <span class="req-chip">Accuracy ≥<strong>${requirements.minAccuracy}%</strong></span>
    <span class="req-chip">Max latency ≤<strong>${requirements.maxLatencyMs}ms</strong></span>
    <span class="req-chip${requirements.auditabilityRequired ? '' : ' off'}">Auditability<strong>${requirements.auditabilityRequired ? 'Required' : 'Not required'}</strong></span>
    <span class="req-chip">Volume<strong>${compact(requirements.monthlyVolume)} / month</strong></span>`;
}

function renderTable(problem, requirements, recommendation) {
  const body = document.querySelector('[data-results-body]');
  if (!body) return;
  body.innerHTML = [...problem.results].sort((a, b) => a.complexityRank - b.complexityRank).map((method) => {
    const passes = methodMeetsRequirements(method, requirements);
    const isWinner = recommendation.winner && method.id === recommendation.winner.id && !recommendation.fallbackUsed;
    return `<tr class="${isWinner ? 'winner-row' : ''}">
      <td><div class="method-cell"><span class="method-badge method-${method.kind}">${method.shortName}</span><div><strong>${method.name}</strong><small>${method.notes}</small></div></div></td>
      <td>${method.accuracy.toFixed(1)}%</td><td>${money(method.costPer1k)}</td><td>${method.latencyMs}ms</td>
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
        return `<a class="rail-item" href="benchmark.html?problem=${entry.slug}">
          <span class="rail-icon" aria-hidden="true">${problemIcon(entry.category)}</span>
          <div><strong>${entry.title}</strong><small>→ <span class="rail-pick">${pick.winner.shortName}</span></small></div>
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
    document.querySelector('[data-latency-value]').textContent = `${requirements.maxLatencyMs} ms`;
    document.querySelector('[data-volume-value]').textContent = compact(requirements.monthlyVolume);
  };

  const render = () => {
    setControls();
    renderRequirementChips(requirements);
    const recommendation = getRecommendation(problem.results, requirements);
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
