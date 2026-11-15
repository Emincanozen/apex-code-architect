# Peak Coding Patterns Reference

Distilled from the #1 densest cluster in the AI Skills Atlas (Frontend/UI,
Backend/API, Testing & QA, Git/PR Engineering).

## 1. Frontend & UI Engineering Patterns
- **Tokenized Theme Contracts**: Always consume semantic CSS variables
  (`--background`, `--foreground`, `--card`, `--primary`) rather than hardcoded
  light/dark utility classes (`bg-slate-900`, `text-white`).
- **Component Boundary Hygiene**: Keep server-side data fetching cleanly
  separated from interactive client state; validate props at boundaries.
- **Zero "AI Slop" Discipline**: Avoid generic uniform card grids, purple
  gradient defaults, and low-contrast placeholder typography.

## 2. Backend, API & Database Patterns
- **Schema-Constrained Validation**: Validate external payloads at entry points
  (e.g., Pydantic v2, Zod, explicit type guards) before business logic runs.
- **Query & Connection Safety**: Use parameterized queries only; prevent N+1
  loops via batched lookups or joins; reuse connection pools.
- **Explicit Error Context**: Propagate typed domain errors rather than
  swallowing exceptions silently.

## 3. Testing & Quality Assurance Patterns
- **Real Behavior Over Mocks**: Test actual execution paths on real temporary
  directories/fixtures whenever feasible (`MockHunter` discipline).
- **Deterministic Assertions**: Seed pseudo-random generators and avoid
  wall-clock timing dependencies in unit tests.

## 4. AST Blast-Radius Thresholds
| Metric | Healthy | Warning | Action Required |
| :--- | :--- | :--- | :--- |
| Function Cyclomatic Complexity | `1 – 6` | `7 – 11` | `>= 12` (Refactor into helpers) |
| File Reverse Dependents (Fan-In) | `0 – 2` | `3 – 5` | `>= 6` (Treat as core contract) |
| Functions per Module | `1 – 12` | `13 – 20` | `> 20` (Split module responsibilities) |
