---
name: shared-audit
description: Audit the current diff for opportunities to use existing shared/common utilities instead of new local helpers. Use before committing code, when adding new utility functions, or when the user says "shared audit", "check shared", or "/shared-audit". Discovers the project's shared-module location from repo conventions — not tied to any specific repo.
---

# Shared-module audit

Goal: catch local helpers in the current diff that duplicate utilities already present in the project's shared/common module. The point is reuse, not style — flag overlap, let the user decide whether to refactor.

## Step 1 — Locate the shared surface

Find where reusable utilities live in this repo. Check in order:

1. `CLAUDE.md`, `AGENTS.md`, or `README.md` at the repo root — look for explicit mentions of "shared", "common library", "utils module", or a documented module catalog.
2. Common directory names at repo root and under `src/`: `shared/`, `lib/`, `common/`, `utils/`, `helpers/`, `core/`, `internal/`, `packages/shared/`, `src/lib/`.
3. For monorepos, look under `packages/*/` or `apps/*/lib/`.

If multiple candidates exist, prefer the one the project's own docs reference. If nothing surfaces, ask the user where shared utilities live before continuing.

## Step 2 — Catalog the shared surface

Build a lightweight index of what's already available. For each shared module, capture **purpose** (one line) and **public functions/classes**. Sources, in preference order:

1. A documented catalog (table in `CLAUDE.md`, `AGENTS.md`, or `shared/README.md`) — trust it as the index.
2. File-level doc comments and the module's public exports (`export`, `__all__`, `module.exports`, public class members, etc.).
3. Function/class signatures (skim, don't read implementations).

Don't read every line of every module. The goal is a function-name-level inventory, not a deep audit.

## Step 3 — Read the diff

Get changed files:

```
git diff --name-only HEAD
git diff --cached --name-only
```

For each changed file in scope (source code, not docs/configs/tests-only), read the diff — focus on added lines. Note new functions, classes, and non-trivial code blocks (loops, retry logic, file ops, format conversions).

If the diff is empty, report so and stop.

## Step 4 — Look for overlaps

For each added piece of code, ask: *is there already something in the shared surface that does this, or could be extended with a parameter to do this?*

Patterns worth flagging:

- **File I/O wrappers** — atomic writes, safe-rename, CSV/JSON append, lockfile patterns
- **HTTP requests** — retry/backoff loops, rate-limit handling, JSON-decode-with-error-handling
- **Date/time** — parsing, formatting, "yesterday/today" helpers, timezone conversion
- **Math & number formatting** — rounding, clamping, normalization, currency/percent formatting
- **String normalization** — name/ID canonicalization, slug generation, escaping/sanitizing
- **Logging setup** — handler/formatter configuration
- **CLI argument parsing** — common flag definitions
- **Caching wrappers** — TTL-based, file-backed
- **Subprocess execution** — run-with-logging patterns
- **UI/DOM helpers** — debounce/throttle, focus trapping, selector wrappers, breakpoint checks
- **CMS/template helpers** — WordPress/Drupal functions, theme partials, or components that already render the same thing
- **Domain-specific conversions** — anything the project's docs flag as having a canonical implementation

This list is a starting point. Adapt to the project's domain. The heuristic: if a new code block feels like infrastructure rather than core feature logic, check whether infra-equivalent already exists.

## Step 5 — Report

Output a checklist. For each finding:

- **Where**: `path/to/file:line` — short description of the local helper
- **Shared equivalent**: `shared/X:func()` — or "extend `shared/X` to accept Y"
- **Confidence**: `high` (exact match), `medium` (close but signature differs), `low` (speculative)

If nothing overlaps, say so explicitly: "Audited N changed files; no shared-module overlaps detected."

Do **not** auto-edit. The user decides whether to refactor. Keep the report scannable — one bullet per finding, no long prose.

## Step 6 — Out of scope

This skill does **not**:

- Refactor or open PRs.
- Audit correctness or security (that's `/code-review`).
- Audit the whole repo — only the current diff.
- Move existing code into shared/ unless asked.
