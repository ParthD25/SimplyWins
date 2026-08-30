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
  let category = 'All';
  const update = () => {
    const query = input.value.toLowerCase().trim();
    const filtered = benchmarkProblems.filter((problem) => (category === 'All' || problem.category === category) && (!query || `${problem.title} ${problem.description} ${problem.category}`.toLowerCase().includes(query)));
    renderProblemCards(grid, filtered);
    const count = document.querySelector('[data-result-count]');
    if (count) count.textContent = filtered.length;
  };
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

function renderScatter(problem, requirements, winner) {
  const host = document.querySelector('[data-scatter]');
  if (!host) return;
  const W = 780, H = 330, m = { top: 24, right: 38, bottom: 54, left: 66 };
  const pw = W - m.left - m.right, ph = H - m.top - m.bottom;
  const maxCost = Math.max(...problem.results.map((x) => x.costPer1k), 10) * 1.6;
  const minCost = 0.005;
  const minAcc = Math.max(60, Math.floor(Math.min(...problem.results.map((x) => x.accuracy), requirements.minAccuracy) / 5) * 5 - 5);
  const x = (cost) => m.left + logScale(cost, minCost, maxCost) * pw;
  const y = (accuracy) => m.top + (1 - (accuracy - minAcc) / (100 - minAcc)) * ph;
  const yTicks = [minAcc, minAcc + (100 - minAcc) / 2, 100];
  const xTicks = [0.01, 0.1, 1, 10].filter((tick) => tick <= maxCost);
  const colors = { rules: '#15966b', 'traditional-ml': '#2457f5', 'small-model': '#7756d8', 'frontier-llm': '#e24a4a' };

  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Accuracy and cost comparison">
    ${yTicks.map((t) => `<line x1="${m.left}" x2="${W-m.right}" y1="${y(t)}" y2="${y(t)}" class="grid-line"/><text x="${m.left-12}" y="${y(t)+4}" text-anchor="end" class="axis-label">${t.toFixed(0)}%</text>`).join('')}
    ${xTicks.map((t) => `<line y1="${m.top}" y2="${H-m.bottom}" x1="${x(t)}" x2="${x(t)}" class="grid-line vertical"/><text x="${x(t)}" y="${H-m.bottom+25}" text-anchor="middle" class="axis-label">$${t}</text>`).join('')}
    <line x1="${m.left}" x2="${W-m.right}" y1="${y(requirements.minAccuracy)}" y2="${y(requirements.minAccuracy)}" class="threshold-line"/>
    <text x="${m.left+8}" y="${y(requirements.minAccuracy)-8}" class="threshold-label">${requirements.minAccuracy}% requirement</text>
    ${problem.results.map((method) => {
      const pass = methodMeetsRequirements(method, requirements);
      const ring = method.id === winner.id ? `<circle cx="${x(method.costPer1k)}" cy="${y(method.accuracy)}" r="15" fill="none" stroke="#15966b" stroke-width="2"/>` : '';
      return `${ring}<circle class="data-point" tabindex="0" data-method="${method.id}" cx="${x(method.costPer1k)}" cy="${y(method.accuracy)}" r="8" fill="${colors[method.kind]}" stroke="#fff" stroke-width="2.5" opacity="${pass ? 1 : .62}"/>`;
    }).join('')}
    <text x="${W/2}" y="${H-10}" text-anchor="middle" class="axis-title">Cost per 1K tasks (USD, log scale)</text>
    <text x="18" y="${H/2}" text-anchor="middle" class="axis-title" transform="rotate(-90 18 ${H/2})">Accuracy</text>
  </svg>`;

  const summary = document.querySelector('[data-chart-summary]');
  const updateSummary = (method) => { if (summary) summary.innerHTML = `<strong>${method.shortName}</strong><span>${method.accuracy.toFixed(1)}% · $${method.costPer1k.toFixed(2)}/1K · ${method.latencyMs}ms</span>`; };
  updateSummary(winner);
  host.querySelectorAll('.data-point').forEach((point) => {
    const method = problem.results.find((m) => m.id === point.dataset.method);
    ['mouseenter','focus','click'].forEach((eventName) => point.addEventListener(eventName, () => updateSummary(method)));
  });
}

function renderTable(problem, requirements, winner) {
  const body = document.querySelector('[data-results-body]');
  if (!body) return;
  body.innerHTML = [...problem.results].sort((a,b) => a.complexityRank - b.complexityRank).map((method) => {
    const passes = methodMeetsRequirements(method, requirements);
    return `<tr class="${method.id === winner.id ? 'winner-row' : ''}">
      <td><div class="method-cell"><span class="method-badge method-${method.kind}">${method.shortName}</span><div><strong>${method.name}</strong><small>${method.notes}</small></div></div></td>
      <td>${method.accuracy.toFixed(1)}%</td><td>$${method.costPer1k.toFixed(2)}</td><td>${method.latencyMs}ms</td>
      <td class="${method.auditable ? 'pass-label':'fail-label'}">${method.auditable ? '✓ Yes':'× No'}</td>
      <td class="${passes ? 'pass-label':'fail-label'}">${passes ? '✓ Pass':'× No'}</td>
    </tr>`;
  }).join('');
}

export function setupBenchmarkPage() {
  const params = new URLSearchParams(location.search);
  const problem = getProblem(params.get('problem') || 'invoice-field-extraction');
  let requirements = structuredClone(problem.requirements);

  const map = {
    title: problem.title,
    category: problem.category,
    description: problem.description,
    question: problem.decisionQuestion,
    dataset: problem.datasetLabel,
    datasetSize: problem.datasetSize,
    rationale: problem.rationale,
  };
  Object.entries(map).forEach(([key,value]) => document.querySelectorAll(`[data-${key}]`).forEach((el) => el.textContent = value));

  const accuracy = document.querySelector('[data-accuracy]');
  const latency = document.querySelector('[data-latency]');
  const volume = document.querySelector('[data-volume]');
  const audit = document.querySelector('[data-audit]');

  const setControls = () => {
    accuracy.value = requirements.minAccuracy; latency.value = requirements.maxLatencyMs; volume.value = requirements.monthlyVolume; audit.checked = requirements.auditabilityRequired;
    document.querySelector('[data-accuracy-value]').textContent = `${requirements.minAccuracy}%`;
    document.querySelector('[data-latency-value]').textContent = `${requirements.maxLatencyMs} ms`;
    document.querySelector('[data-volume-value]').textContent = Intl.NumberFormat('en-US',{notation:'compact'}).format(requirements.monthlyVolume);
  };

  const render = () => {
    setControls();
    const rec = getRecommendation(problem.results, requirements);
    const monthly = rec.winner.costPer1k * (requirements.monthlyVolume / 1000);
    document.querySelector('[data-rec-label]').textContent = rec.fallbackUsed ? 'Closest current option' : 'Simplest passing recommendation';
    document.querySelector('[data-rec-name]').textContent = rec.winner.name;
    document.querySelector('[data-rec-reason]').textContent = rec.reason;
    document.querySelector('[data-rec-accuracy]').textContent = `${rec.winner.accuracy.toFixed(1)}%`;
    document.querySelector('[data-rec-latency]').textContent = `${rec.winner.latencyMs}ms`;
    document.querySelector('[data-rec-monthly]').textContent = `$${monthly.toFixed(2)}`;
    document.querySelector('.recommendation-banner').classList.toggle('recommendation-warning', rec.fallbackUsed);
    renderScatter(problem, requirements, rec.winner);
    renderTable(problem, requirements, rec.winner);
  };

  accuracy.addEventListener('input', () => { requirements.minAccuracy = Number(accuracy.value); render(); });
  latency.addEventListener('input', () => { requirements.maxLatencyMs = Number(latency.value); render(); });
  volume.addEventListener('input', () => { requirements.monthlyVolume = Number(volume.value); render(); });
  audit.addEventListener('change', () => { requirements.auditabilityRequired = audit.checked; render(); });
  document.querySelector('[data-reset]').addEventListener('click', () => { requirements = structuredClone(problem.requirements); render(); });
  render();
}

export { benchmarkProblems };
