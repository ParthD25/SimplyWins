# Build Decisions

## Why the frontend is dependency-free for v0.1
The visual prototype is delivered as static HTML/CSS/ES modules so it can be opened, reviewed, hosted on Vercel, and connected to a Python API without requiring a JavaScript package build. This keeps the first portfolio artifact simple and prevents frontend tooling from becoming the project.

If the application later needs authentication, complex client-side routing, large shared state, or live benchmark-run orchestration, migrate the frontend to React/Next.js deliberately. Do not migrate merely because React is fashionable.

## Why the benchmark chart is custom SVG
The MVP has one primary scatterplot with four points per benchmark. A chart library would add bundle/dependency complexity without meaningful benefit. The SVG remains accessible through a table fallback and keyboard-focusable data points.

## Why the backend is separate
Benchmark execution is Python-centric (pandas, scikit-learn, evaluation tooling, document processing). A FastAPI service keeps benchmark code close to the Python ecosystem while the frontend remains independently deployable.
