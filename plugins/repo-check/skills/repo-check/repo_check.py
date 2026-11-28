#!/usr/bin/env python3
"""Report what needs action across a GitHub owner's repos.

Checks every non-archived repo for open Dependabot alerts, code-scanning
alerts, secret-scanning alerts and open Dependabot PRs, plus repos that have
dependency files but Dependabot alerts turned off. Prints only what needs
action, then a footer with counts so a quiet run is distinguishable from a
broken one.

Usage:
    repo_check.py [--owner OWNER] [--json]

Exit codes: 0 nothing to do, 1 something needs action, 2 errors occurred.

Repos listed (one "owner/name" per line, # comments allowed) in
$REPO_CHECK_IGNORE, default ~/.config/repo-check/ignore, are left out of the
"alerts off" list only; their alerts and PRs are still reported.

Requires the GitHub CLI (`gh`), logged in with the `repo` scope.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

MANIFEST_RE = re.compile(
    r"(^|/)(package\.json|composer\.json|requirements[^/]*\.txt|Pipfile|pyproject\.toml"
    r"|Gemfile|go\.mod|Cargo\.toml|Package\.swift|pom\.xml|build\.gradle(\.kts)?"
    r"|\.github/workflows/[^/]+\.ya?ml)$"
)
SKIP_DIRS = ("node_modules/", "vendor/")
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "moderate": 2, "low": 3, "warning": 3,
                  "note": 4, "error": 1}
BUMP_RE = re.compile(r"from v?(\d+)(?:\.(\d+))?\S* to v?(\d+)(?:\.(\d+))?")


def bump_kind(title):
    """'major', 'minor' (minor or patch) or 'unknown' for a Dependabot PR title.

    Grouped PRs ("bump the npm group ... with 5 updates") don't say, so they are
    'unknown'. Under semver a 0.x minor bump (0.27 -> 0.28) may break, so it counts
    as major.
    """
    m = BUMP_RE.search(title)
    if not m:
        return "unknown"
    old_major, old_minor, new_major, new_minor = m.groups()
    if old_major != new_major:
        return "major"
    if old_major == "0" and old_minor != new_minor:
        return "major"
    return "minor"


class GhError(Exception):
    def __init__(self, status, message):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


def gh_json(args):
    """Run a gh command and return parsed JSON, raising GhError on failure."""
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        m = re.search(r"\(HTTP (\d{3})\)", proc.stderr)
        status = int(m.group(1)) if m else 0
        message = proc.stderr.strip().removeprefix("gh: ")
        message = re.sub(r"\s*\(HTTP \d{3}\)\s*$", "", message.splitlines()[0] if message else "")
        raise GhError(status, message or "gh failed")
    out = proc.stdout.strip()
    return json.loads(out) if out else None


def gh_api_list(path):
    """GET every page of a list endpoint."""
    pages = gh_json(["api", "--paginate", "--slurp", path])
    return [item for page in pages or [] for item in page]


def classify_off(err, patterns):
    """True if the error means the feature is simply not enabled."""
    return err.status in (403, 404) and any(p in err.message.lower() for p in patterns)


def check_repo(repo):
    name = repo["nameWithOwner"]
    result = {"repo": name, "url": repo["url"], "dependabot": None, "code_scanning": None,
              "secret_scanning": None, "prs": [], "manifests": [], "errors": []}

    try:
        alerts = gh_api_list(f"repos/{name}/dependabot/alerts?state=open&per_page=100")
        result["dependabot"] = [{
            "severity": a["security_advisory"]["severity"],
            "package": a["dependency"]["package"]["name"],
            "ecosystem": a["dependency"]["package"]["ecosystem"],
            "manifest": a["dependency"].get("manifest_path"),
            "summary": a["security_advisory"]["summary"],
            "patched": (a.get("security_vulnerability") or {}).get("first_patched_version") or {},
            "url": a["html_url"],
        } for a in alerts]
    except GhError as e:
        if not classify_off(e, ["disabled"]):
            result["errors"].append(f"dependabot alerts: {e}")

    try:
        alerts = gh_api_list(f"repos/{name}/code-scanning/alerts?state=open&per_page=100")
        result["code_scanning"] = [{
            "severity": (a["rule"].get("security_severity_level") or a["rule"].get("severity") or "note"),
            "rule": a["rule"].get("description") or a["rule"].get("id"),
            "path": a.get("most_recent_instance", {}).get("location", {}).get("path"),
            "url": a["html_url"],
        } for a in alerts]
    except GhError as e:
        if not classify_off(e, ["no analysis found", "not enabled", "advanced security"]):
            result["errors"].append(f"code scanning: {e}")

    try:
        alerts = gh_api_list(f"repos/{name}/secret-scanning/alerts?state=open&per_page=100")
        result["secret_scanning"] = [{
            "type": a.get("secret_type_display_name") or a.get("secret_type"),
            "created": a.get("created_at", "")[:10],
            "url": a["html_url"],
        } for a in alerts]
    except GhError as e:
        if not classify_off(e, ["disabled", "not enabled", "advanced security"]):
            result["errors"].append(f"secret scanning: {e}")

    try:
        prs = gh_json(["pr", "list", "-R", name, "--author", "app/dependabot", "--state", "open",
                       "--limit", "100",
                       "--json", "number,title,url,createdAt,isDraft,mergeable,statusCheckRollup"])
        now = datetime.now(timezone.utc)
        for p in prs or []:
            checks = p.get("statusCheckRollup") or []
            states = {(c.get("conclusion") or c.get("state") or c.get("status") or "").upper()
                      for c in checks}
            if states & {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}:
                check_state = "failing"
            elif states & {"PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED", "WAITING"}:
                check_state = "pending"
            elif checks:
                check_state = "passing"
            else:
                check_state = "none"
            created = datetime.fromisoformat(p["createdAt"].replace("Z", "+00:00"))
            # Dependabot security PRs have the same titles as version updates, so match
            # the title against this repo's open alert packages instead.
            fixes = sorted({a["package"] for a in result["dependabot"] or []
                            if re.search(rf"\bbump {re.escape(a['package'].lower())}(?=\s|$)",
                                         p["title"].lower())})
            result["prs"].append({
                "number": p["number"], "title": p["title"], "url": p["url"],
                "age_days": (now - created).days, "checks": check_state,
                "bump": bump_kind(p["title"]), "conflicts": p.get("mergeable") == "CONFLICTING",
                "fixes_alerts_for": fixes,
            })
    except GhError as e:
        result["errors"].append(f"dependabot PRs: {e}")

    # Only look for dependency files when Dependabot alerts are off. Forks are skipped:
    # upstream maintains their dependencies.
    if result["dependabot"] is None and not repo.get("isFork") and repo.get("defaultBranchRef"):
        branch = repo["defaultBranchRef"]["name"]
        try:
            tree = gh_json(["api", f"repos/{name}/git/trees/{branch}?recursive=1"])
            found = set()
            for t in tree.get("tree", []):
                path = t["path"]
                if t.get("type") != "blob" or any(d in path for d in SKIP_DIRS):
                    continue
                if not MANIFEST_RE.search(path):
                    continue
                if path.startswith(".github/workflows/"):
                    found.add("GitHub Actions workflows")
                else:
                    found.add(path.rsplit("/", 1)[-1])
            result["manifests"] = sorted(found)
        except GhError as e:
            if e.status != 409:  # 409 = empty repo
                result["errors"].append(f"file tree: {e}")

    return result


def load_ignore():
    path = os.environ.get("REPO_CHECK_IGNORE", os.path.expanduser("~/.config/repo-check/ignore"))
    try:
        with open(path) as f:
            return {line.split("#")[0].strip().lower() for line in f if line.split("#")[0].strip()}
    except FileNotFoundError:
        return set()


def sev_key(item):
    return SEVERITY_ORDER.get(str(item.get("severity", "")).lower(), 9)


def print_report(owner, results, ignore):
    actionable = 0
    for r in results:
        lines = []
        for a in sorted(r["dependabot"] or [], key=sev_key):
            fix = a["patched"].get("identifier")
            lines.append(f"  [dependabot {a['severity']}] {a['package']} ({a['ecosystem']}): "
                         f"{a['summary']}" + (f" -> fixed in {fix}" if fix else " -> no fix yet")
                         + f"\n      {a['url']}")
        for a in sorted(r["code_scanning"] or [], key=sev_key):
            lines.append(f"  [code scanning {a['severity']}] {a['rule']}"
                         + (f" in {a['path']}" if a["path"] else "") + f"\n      {a['url']}")
        for a in r["secret_scanning"] or []:
            lines.append(f"  [secret] {a['type']} exposed since {a['created']}\n      {a['url']}")
        for p in sorted(r["prs"], key=lambda p: -p["age_days"]):
            flags = [f"{p['age_days']}d old", f"checks {p['checks']}"]
            if p["bump"] == "major":
                flags.append("MAJOR version")
            elif p["bump"] == "unknown":
                flags.append("bump size unknown")
            if p["conflicts"]:
                flags.append("merge conflicts")
            if p["fixes_alerts_for"]:
                flags.append("fixes alerts for " + ", ".join(p["fixes_alerts_for"]))
            lines.append(f"  [PR #{p['number']}] {p['title']} ({', '.join(flags)})\n      {p['url']}")
        if lines:
            actionable += 1
            print(f"{r['repo']}")
            print("\n".join(lines))
            print()

    off = [r for r in results if r["dependabot"] is None and r["manifests"]
           and r["repo"].lower() not in ignore]
    if off:
        print("Dependabot alerts off, but the repo has dependency files:")
        for r in off:
            print(f"  {r['repo']}: {', '.join(r['manifests'])}")
            print(f"      enable: gh api -X PUT repos/{r['repo']}/vulnerability-alerts")
        print()

    errors = [(r["repo"], e) for r in results for e in r["errors"]]
    if errors:
        print("Errors (these repos were not fully checked):")
        for repo, e in errors:
            print(f"  {repo}: {e}")
        print()

    n_on = sum(r["dependabot"] is not None for r in results)
    n_alerts = sum(len(r["dependabot"] or []) + len(r["code_scanning"] or [])
                   + len(r["secret_scanning"] or []) for r in results)
    n_prs = sum(len(r["prs"]) for r in results)
    if not actionable and not off and not errors:
        print(f"Nothing to do for {owner}.")
    print(f"Checked {len(results)} repos of {owner} (archived skipped) · "
          f"Dependabot alerts on {n_on}, off {len(results) - n_on} · "
          f"{n_alerts} open alerts · {n_prs} Dependabot PRs · "
          f"{len(off)} unmonitored with dependencies · {len(errors)} errors")
    if errors:
        return 2
    return 1 if (actionable or off) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--owner", help="GitHub user or org (default: the logged-in gh user)")
    ap.add_argument("--json", action="store_true", help="print raw results as JSON")
    args = ap.parse_args()

    try:
        owner = args.owner or gh_json(["api", "user"])["login"]
        gh_json(["api", f"users/{owner}"])  # fails loudly for a mistyped owner
        repos = gh_json(["repo", "list", owner, "--limit", "1000", "--no-archived",
                         "--json", "nameWithOwner,url,defaultBranchRef,isFork"])
    except GhError as e:
        print(f"repo-check: could not list repos for {args.owner or 'the gh user'}: {e}",
              file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("repo-check: the GitHub CLI (gh) is not installed", file=sys.stderr)
        return 2
    if not repos:
        print(f"repo-check: {owner} has no non-archived repos visible to this gh login",
              file=sys.stderr)
        return 2

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = sorted(pool.map(check_repo, repos), key=lambda r: r["repo"].lower())

    ignore = load_ignore()
    if not args.json:
        return print_report(owner, results, ignore)

    for r in results:
        r["ignored"] = r["repo"].lower() in ignore
    print(json.dumps({"owner": owner, "repos": results}, indent=2))
    if any(r["errors"] for r in results):
        return 2
    needs_action = any(r["dependabot"] or r["code_scanning"] or r["secret_scanning"] or r["prs"]
                       or (r["dependabot"] is None and r["manifests"] and not r["ignored"])
                       for r in results)
    return 1 if needs_action else 0


if __name__ == "__main__":
    sys.exit(main())
