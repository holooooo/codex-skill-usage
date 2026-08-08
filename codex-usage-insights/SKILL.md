---
name: codex-usage-insights
description: Analyze local Codex session logs over a selectable date range, summarize usage by skill, identify skills with no observed use, and generate an animated HTML report plus JSON data. Use when the user asks for Codex usage analytics, skill adoption reports, recent activity summaries, or a visual static dashboard generated with Python.
---

# Codex Usage Insights

Use the bundled Python CLI to turn local Codex JSONL session logs into a
portable report. The default window is the last seven calendar days; pass
`--days`, or an inclusive `--start` and `--end`, when a different window is
needed.

## Quick start

```bash
python3 /path/to/codex-usage-insights/scripts/codex_usage_report.py
```

The command writes an HTML file and, when `--data-output` is supplied, a JSON
file beside it. The page fetches that JSON when served over HTTP and keeps an
embedded fallback for direct file previews. Use `--output` to choose another
HTML path.

When running in the Codex desktop app, after the command succeeds, prioritize
showing the generated report in the right sidebar browser before replying:

```js
codex_app__open_in_codex({
  placement: "right",
  target: {
    type: "browser",
    url: "file:///absolute/path/to/codex-usage-insights/report.html"
  }
})
```

Use the resolved absolute path and a URL-encoded `file://` URL. If the sidebar
browser cannot open the local file, retry with the same path as a `type: "file"`
target. In non-desktop environments, report the absolute output path instead;
do not open a separate system browser first.

## Workflow

1. Discover `.jsonl` files under `~/.codex/sessions` and
   `~/.codex/archived_sessions` unless `--sessions-root` is supplied.
2. Read event timestamps and user/assistant `response_item` content. Ignore
   `session_meta`, `turn_context`, tool schemas, and system instructions.
3. Detect explicit skill references (`$skill-name`, `/skill-name`, a
   `skills/<name>/SKILL.md` path, or a known skill name in a user/assistant
   message). Aggregate mentions, sessions, and first/last seen timestamps.
4. Discover installed skills from the default Codex skill roots plus any
   repeated `--skills-root` values. Match their frontmatter `name` values
   against observed usage to produce `unused_skills`.
5. Render the result through `assets/report.html`; preserve the report data
   contract when customizing the visual layer.
6. After a successful render, open the output in the Codex sidebar browser as
   described above before returning the completion message.

## Evidence and limits

The report is an observation of local JSONL logs, not a billing or server-side
usage record. A skill is considered used only when its name is explicitly
observable in a message during the selected window. Tool calls that omit a
skill name remain unclassified. The report always displays the source roots,
file count, and coverage window so the result is auditable.

## Custom report data

The renderer consumes a single JSON object with `period`, `generated_at`,
`totals`, `skill_usage`, `projects`, `unused_skills`, `timeline`, and `sources`
fields. Each `timeline` item contains a `projects` map keyed by the stable
project ID; each project value contains `messages`, `sessions`, and a `skills`
counter. Keep these fields when replacing the template or adding a new
renderer so project/skill trend filters remain functional.
