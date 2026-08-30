#!/usr/bin/env bash
#
# Every check CI runs, runnable locally with the same commands.
#
# CI calls into this script rather than repeating the commands in YAML, so the
# two cannot drift: if this passes on your machine, that is the same set of
# checks the workflow runs. Usage:
#
#   scripts/ci.sh            # everything
#   scripts/ci.sh backend    # backend only
#   scripts/ci.sh frontend   # frontend only
#
# Assumes the backend's dependencies are already installed (pip install -e
# ".[dev]"), which is what the workflow does in its own step.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${1:-all}"

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

run_backend() {
  cd "$repo_root/backend"

  step "Lint"
  ruff check .

  step "Format"
  ruff format --check .

  step "Types"
  mypy app

  # A model change without a migration reaches development but never
  # production; this is what catches it.
  step "Migrations match models"
  export SIMPLESTWINS_DATABASE_URL="${SIMPLESTWINS_DATABASE_URL:-sqlite+pysqlite:///./ci.db}"
  alembic upgrade head
  alembic check

  step "Tests"
  pytest -q

  # The runner is a deliverable, so a change that breaks it must fail here
  # rather than being discovered the next time someone runs a benchmark.
  step "Benchmark smoke test"
  python -m app.benchmarks.cli run support-ticket-routing --method ticket-rules
}

run_frontend() {
  cd "$repo_root"

  # `node --check <file>` is not usable here: for a .js file Node detects as an
  # ES module it returns 0 without parsing at all, so it passed `export const
  # a = = 1`. Every frontend module is ESM, which made the check inert. Feeding
  # the source in with --input-type=module forces a real parse; the filename is
  # printed here because that route reports errors against "[stdin]".
  #
  # Failures are collected rather than relied on loop exit status, which
  # reports only the last file: a broken api.js would otherwise pass as long as
  # data.js parsed.
  step "Syntax check"
  local failed=()
  for f in frontend/assets/*.js; do
    if node --input-type=module --check < "$f"; then
      printf 'ok: %s\n' "$f"
    else
      printf 'SYNTAX ERROR in %s (reported above as [stdin])\n' "$f" >&2
      failed+=("$f")
    fi
  done
  if [ ${#failed[@]} -gt 0 ]; then
    printf 'Syntax errors in: %s\n' "${failed[*]}" >&2
    return 1
  fi

  step "Render checks"
  node ci/render-check.mjs
}

case "$target" in
  backend)  run_backend ;;
  frontend) run_frontend ;;
  all)      run_backend; run_frontend ;;
  *)        echo "usage: scripts/ci.sh [backend|frontend|all]" >&2; exit 2 ;;
esac

printf '\n\033[1mAll checks passed.\033[0m\n'
