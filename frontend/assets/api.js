/**
 * Backend client with an offline fallback.
 *
 * The backend is authoritative once reachable: it owns the seed and the
 * decision rule. When it is not configured or not reachable, the site falls
 * back to the bundled `data.js` so the static prototype still works — a
 * portfolio page hosted on Vercel with no API behind it must still render.
 *
 * The fallback is announced, never silent. A visitor reading numbers deserves
 * to know whether they came from the service or from a bundled copy.
 */
import { benchmarkProblems } from './data.js';

const CONFIGURED_BASE = (globalThis.SIMPLESTWINS_API_BASE ?? '').replace(/\/$/, '');
const TIMEOUT_MS = 4000;

export const SOURCE = { API: 'api', BUNDLED: 'bundled' };

/** Bundled problems, shaped as the API returns them. */
function bundled() {
  return benchmarkProblems.map((problem) => ({ ...problem, source: SOURCE.BUNDLED }));
}

async function request(path) {
  if (!CONFIGURED_BASE) return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${CONFIGURED_BASE}${path}`, {
      signal: controller.signal,
      headers: { accept: 'application/json' },
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    // Unreachable, timed out, or blocked by CORS — all mean "fall back".
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** Translate an API problem into the shape the UI already renders. */
function fromApi(problem) {
  return {
    slug: problem.slug,
    title: problem.title,
    category: problem.category,
    description: problem.description,
    decisionQuestion: problem.decision_question,
    datasetLabel: problem.dataset.name,
    datasetSize: problem.dataset.sample_count_label,
    status: problem.status,
    rationale: problem.rationale,
    requirements: {
      minAccuracy: problem.default_requirements.min_accuracy,
      maxLatencyMs: problem.default_requirements.max_latency_ms,
      auditabilityRequired: problem.default_requirements.auditability_required,
      monthlyVolume: problem.default_requirements.monthly_volume,
    },
    results: problem.methods.map((method) => ({
      id: method.method_id,
      name: method.name,
      shortName: method.short_name,
      kind: method.method_class,
      accuracy: method.result.accuracy,
      costPer1k: method.result.cost_per_1k,
      latencyMs: method.result.latency_p50_ms,
      deterministic: method.result.deterministic,
      auditable: method.result.auditable,
      complexityRank: method.complexity_rank,
      resultState: method.result.result_state,
      runId: method.result.run_id,
      notes: method.notes,
    })),
    source: SOURCE.API,
  };
}

/** Summary shape for listings: enough to render a card, one request total. */
function summaryFromApi(summary) {
  return {
    slug: summary.slug,
    title: summary.title,
    category: summary.category,
    description: summary.description,
    decisionQuestion: summary.decision_question,
    status: summary.status,
    measuredCount: summary.measured_count,
    methodCount: summary.method_count,
    results: [],
    source: SOURCE.API,
  };
}

/**
 * Problem summaries, from the API when available.
 *
 * Deliberately one request. The listing carries the evidence counts a card
 * needs, so fetching each problem in full to render a list would be six extra
 * round trips for data the page never shows.
 */
export async function loadProblems() {
  const listing = await request('/v1/problems');
  if (!listing) return bundled();
  return listing.problems.map(summaryFromApi);
}

/** One problem, from the API when available. */
export async function loadProblem(slug) {
  const detail = await request(`/v1/problems/${slug}`);
  if (detail) return fromApi(detail);
  return bundled().find((problem) => problem.slug === slug) ?? bundled()[0];
}

export function isConfigured() {
  return Boolean(CONFIGURED_BASE);
}
