# nhall-skills

Claude Code skills I've written and use every day, packaged as a plugin marketplace.

## Install

```sh
claude plugin marketplace add nhall/nhall-skills
claude plugin install shared-audit@nhall-skills
claude plugin install repo-check@nhall-skills
claude plugin install timemap@nhall-skills
```

Install only the ones you want. Auto-update is off by default for marketplaces outside Anthropic's; turn it on in `/plugin` → Marketplaces to get new versions automatically. Skills trigger on their own when a request matches, or run them as `/<plugin>:<skill>`.

## Skills

| Plugin | What it does |
|---|---|
| [`shared-audit`](plugins/shared-audit/skills/shared-audit/SKILL.md) | Before you commit, checks the diff for new helpers that duplicate utilities the project already has in its shared or common code, and reports matches by confidence. Reports only; it never edits. |
| [`repo-check`](plugins/repo-check/skills/repo-check/SKILL.md) | Checks every non-archived repo you own on GitHub for open Dependabot, code-scanning and secret-scanning alerts, open Dependabot PRs, and repos with dependencies but alerts off. It ranks what needs action and suggests a next step for each; changes happen only when you ask. The bundled `repo_check.py` also runs on its own from a terminal (needs `gh`). |
| [`timemap`](https://github.com/nhall/timemap) | Turns a day of Claude Code sessions into a Time Map: hours per ticket, overlap between parallel sessions, and gaps with no activity. Lives in its own repo. |

Bigger skills get their own repo and are listed here by reference, so this marketplace is the one place to find everything.

## License

MIT
