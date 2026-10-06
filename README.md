# nhall-skills

Claude Code skills I've written and use every day, packaged as a plugin marketplace.

## Install

```sh
claude plugin marketplace add nhall/nhall-skills
claude plugin install shared-audit@nhall-skills
claude plugin install timemap@nhall-skills
claude plugin install unslop@nhall-skills
```

Install only the ones you want. Auto-update is off by default for marketplaces outside Anthropic's; turn it on in `/plugin` → Marketplaces to get new versions automatically. Skills trigger on their own when a request matches, or run them as `/<plugin>:<skill>`.

## Skills

| Plugin | What it does |
|---|---|
| [`shared-audit`](plugins/shared-audit/skills/shared-audit/SKILL.md) | Before you commit, checks the diff for new helpers that duplicate utilities the project already has in its shared or common code, and reports matches by confidence. Reports only; it never edits. |
| [`timemap`](https://github.com/nhall/timemap) | Turns a day of Claude Code sessions into a Time Map: hours per ticket, overlap between parallel sessions, and gaps with no activity. Lives in its own repo. |
| [`unslop`](https://github.com/theclaymethod/unslop) | Finds formulaic or unclear writing and makes targeted edits that keep the meaning and voice. Third-party, by theclaymethod. Listed here by reference so it installs and updates like the rest. |

Bigger skills get their own repo and are listed here by reference, so this marketplace is the one place to find everything.

## License

MIT
