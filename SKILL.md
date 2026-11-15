---
name: apex-code-architect
description: >-
  Deterministic multi-file code engineering, AST blast-radius mapping, and
  automated verification workflow covering the most saturated domain in the AI
  skills ecosystem (Frontend/Backend coding, testing, and Git quality). Use when
  architecting new modules, refactoring multi-file repositories, auditing
  cyclomatic complexity, or enforcing pre-commit code quality gates.
---

# Apex Code Architect (Peak-Domain Skill)

This skill distills the proven architectural standards from the highest-density
clusters of the AI skills ecosystem (`frontend-design`, `awesome-cursorrules`,
`database-optimization`, `webapp-testing`, and `github-ready`) into one
executable, deterministic engineering protocol.

## Mandatory Negative Constraints

Never violate these rules while synthesizing or refactoring code:
1. **No Blind Multi-File Edits**: Never edit shared helpers, schemas, or API
   contracts before calculating their AST blast radius and reverse dependents.
2. **No Silent Complexity Spikes**: Never introduce functions with cyclomatic
   complexity above `12` or deep nesting (`> 3` levels) without splitting helpers.
3. **No Generic Placeholder Scaffolds**: Never leave `TODO`, mocked stubs, or
   hardcoded credentials inside production paths.
4. **No Unverified Claims**: Never report a module as working without running
   automated tests or syntax/AST validation after the final edit.

---

## 5-Stage Deterministic Engineering Workflow

### Stage 1: AST Blast-Radius Mapping
Before touching code in an existing repository, map its dependency topology and
complexity hotspots using the bundled AST analyzer:

```bash
python ./scripts/ast_blast_radius.py <target_dir> --format markdown
```

Review the output for:
- **Hub Files (High Reverse-Dependency Count)**: Changes here ripple across
  downstream modules; require strict interface preservation.
- **Complexity Hotspots (`complexity >= 10`)**: Candidates for decomposition.

### Stage 2: Contract-First Atomic Synthesis
1. Define data contracts, types, and boundary schemas first.
2. Keep each function single-purpose (`<= 35` lines target) with shallow early
   returns instead of nested `if/else` ladders.
3. Extract shared patterns into parameterized helpers rather than duplicating
   near-identical code blocks.
4. Consult [Peak Coding Patterns](./references/peak_coding_patterns.md) for
   frontend, backend, and testing invariants.

### Stage 3: Edge-Case & Unit Verification
1. Write deterministic unit tests covering boundary inputs, empty states,
   error branches, and round-trip invariants.
2. Execute the project test suite cleanly (`python -m unittest`, `pytest`, or
   `npm test`).

### Stage 4: Complexity & Hygiene Gate
Re-run the AST analyzer after your edits to verify no complexity regressions or
broken imports were introduced:

```bash
python ./scripts/ast_blast_radius.py <target_dir> --max-complexity 12 --strict
```

### Stage 5: Self-Repair Loop (Max 2 Attempts)
If Stage 3 or Stage 4 fails:
1. Inspect the exact failing AST node, line number, or assertion diff.
2. Apply a surgical fix targeting the root cause (never silence errors with
   broad `try/except: pass` blocks).
3. Re-run Stages 3 and 4 until exit code `0`.
