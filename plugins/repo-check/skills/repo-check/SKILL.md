---
name: repo-check
description: Check every non-archived GitHub repo an owner has for anything that needs action — open Dependabot, code-scanning and secret-scanning alerts, open Dependabot PRs, and repos with dependencies but Dependabot alerts off — then triage it. Use when the user says "repo check", "check my repos", "any vulns", "dependabot status", or "/repo-check".
---

# Repo check

Goal: one pass over all of an owner's repos that reports only what needs action, ranked, with a suggested next step for each item. Report first; change nothing without the user's yes.

## Step 1: Gather

Run the bundled script. It needs `gh` logged in with the `repo` scope.

```
python3 <skill base directory>/repo_check.py --json
```

Add `--owner <org>` only if the user names one; the default is the logged-in `gh` user. Exit codes: 0 nothing to do, 1 something needs action, 2 errors.

Each repo in the JSON has:

- `dependabot`, `code_scanning`, `secret_scanning`: a list of open alerts, or `null` when that feature is off for the repo (not the same as an empty list).
- `prs`: open Dependabot PRs with `age_days`, `checks` (passing, failing, pending, none), `major`, `conflicts`, `security`.
- `manifests`: dependency files found, only filled in when Dependabot alerts are off and the repo isn't a fork.
- `ignored`: true when the user listed the repo in `~/.config/repo-check/ignore` (or `$REPO_CHECK_IGNORE`) as deliberately unmonitored. Don't report its `manifests`.
- `errors`: checks that failed. A repo with errors was not fully checked.

If the script exits 2 or any repo has `errors`, say which checks failed before anything else. Never report "nothing to do" while errors exist.

## Step 2: Triage

Rank in this order:

1. **Secret-scanning alerts.** A leaked credential. Tell the user to rotate it first, then close the alert.
2. **Critical and high alerts** (Dependabot or code scanning).
3. **Medium and low alerts.**
4. **Dependabot PRs.**
5. **Unmonitored repos** (alerts off, has `manifests`, not `ignored`).

While ranking:

- Group Dependabot alerts by package. Several alerts often share one fix ("update vite to 6.4.4 closes 5 alerts"). Say what to update to, from `patched`.
- Match alerts to open PRs. If a Dependabot PR already bumps the vulnerable package, the action is "merge PR #N", not a manual update.
- For each PR give a verdict:
  - Safe to merge: patch or minor, checks passing, no conflicts.
  - Review first: `major` is true (read the changelog for breaking changes), or checks are failing or `none`.
  - Needs rebase: `conflicts` is true. Comment `@dependabot rebase` on the PR.
  - Mention any PR open more than 30 days as stale.
- For an unmonitored repo, ask whether the dependencies there are installed or deployed. If not, offer to add it to the ignore file rather than enabling alerts.

## Step 3: Report

Lead with one line: counts of alerts by severity, PRs, and repos checked (from the script's totals). Then a short list, most urgent first. Each item gets the repo, what it is, the link, and the suggested action. Leave out repos with nothing to report.

If nothing needs action and there are no errors, say so in one line with the repo count.

## Step 4: Act only on request

Offer the next steps, but run none until the user says which:

- Merge a PR: `gh pr merge <n> -R <repo> --squash` (or the repo's usual merge method).
- Rebase a PR: `gh pr comment <n> -R <repo> --body "@dependabot rebase"`.
- Enable alerts: `gh api -X PUT repos/<repo>/vulnerability-alerts`.
- Dismiss an alert: needs a reason from the user; use `gh api -X PATCH repos/<repo>/dependabot/alerts/<n> -f state=dismissed -f dismissed_reason=<reason>`.

After any change, re-run the script for that owner and confirm the item is gone.

## Out of scope

- Archived repos. The script skips them.
- Fixing vulnerable code by hand. Point the user to the repo; don't edit it from here.
- Dependabot update-job failures (a broken `dependabot.yml`, registry auth). GitHub exposes those only on each repo's Insights → Dependency graph → Dependabot page.
