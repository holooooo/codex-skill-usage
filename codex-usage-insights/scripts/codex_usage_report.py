#!/usr/bin/env python3
"""Build a self-contained Codex skill usage report from local JSONL logs."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


UTC = dt.timezone.utc
SKILL_RE = re.compile(r"(?:\$|/)([a-z0-9][a-z0-9-]*(?::[a-z0-9][a-z0-9-]*)?)", re.I)
PATH_RE = re.compile(r"skills/([^/\s`]+?)/SKILL\.md", re.I)
USAGE_RE = re.compile(
    r"(?:using|use|with|skill|技能|使用|调用)\s*[:：]?\s*[`$]?([a-z][a-z0-9-]*(?::[a-z][a-z0-9-]*)?)",
    re.I,
)


def parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso_date(value: dt.datetime) -> str:
    return value.astimezone(UTC).date().isoformat()


def json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(json_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(json_text(item) for item in value.values())
    return ""


def iter_message_text(record: dict[str, Any]) -> Iterable[str]:
    """Yield only conversational text, never system/tool metadata."""
    if record.get("type") != "response_item":
        return
    payload = record.get("payload") or {}
    role = payload.get("role")
    if role not in {"user", "assistant"}:
        return
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"input_text", "output_text", "text"}:
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    yield text
    elif isinstance(content, str) and content.strip():
        yield content


def discover_log_files(roots: Iterable[Path], start: dt.datetime | None = None, end: dt.datetime | None = None) -> list[Path]:
    files: set[Path] = set()
    start_day = start.date() if start else None
    end_day = end.date() if end else None
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.jsonl"):
            if not path.is_file():
                continue
            if start_day and end_day:
                # Session roots use YYYY/MM/DD directories; archived roots put
                # the same date in the rollout filename. Skip impossible days
                # before opening large JSONL files.
                match = re.search(r"(?:^|[/_-])(20\d{2})[/_-](\d{2})[/_-](\d{2})(?:[/_T-]|$)", str(path))
                if match:
                    try:
                        file_day = dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                    except ValueError:
                        file_day = None
                    if file_day and not (start_day <= file_day <= end_day):
                        continue
            files.add(path)
    return sorted(files)


def discover_skills(roots: Iterable[Path]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        for skill_file in root.rglob("SKILL.md"):
            try:
                text = skill_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            match = re.search(r"^name:\s*([^\n#]+)", text, re.M)
            name = match.group(1).strip().strip("'\"") if match else skill_file.parent.name
            if name:
                found.setdefault(name, skill_file)
    return found


def extract_mentions(text: str, known_lookup: dict[str, str], known_pattern: re.Pattern[str] | None) -> set[str]:
    mentions: set[str] = set()
    for match in SKILL_RE.finditer(text):
        candidate = known_lookup.get(match.group(1).casefold())
        if candidate:
            mentions.add(candidate)
    for match in PATH_RE.finditer(text):
        candidate = known_lookup.get(match.group(1).casefold())
        if candidate:
            mentions.add(candidate)
    for match in USAGE_RE.finditer(text):
        candidate = known_lookup.get(match.group(1).casefold())
        if candidate:
            mentions.add(candidate)
    # Known names are matched only as standalone tokens in conversational text;
    # this captures assistant messages that say "using the gsap-core skill".
    if known_pattern:
        for match in known_pattern.finditer(text):
            candidate = known_lookup.get(match.group(1).casefold())
            if candidate:
                mentions.add(candidate)
    return mentions


def analyze(
    files: list[Path],
    skills: dict[str, Path],
    start: dt.datetime,
    end: dt.datetime,
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    session_ids: defaultdict[str, set[str]] = defaultdict(set)
    first_seen: dict[str, dt.datetime] = {}
    last_seen: dict[str, dt.datetime] = {}
    daily_sessions: defaultdict[str, set[str]] = defaultdict(set)
    daily_messages: Counter[str] = Counter()
    daily_skills: defaultdict[str, set[str]] = defaultdict(set)
    daily_project_messages: defaultdict[str, Counter[str]] = defaultdict(Counter)
    daily_project_sessions: defaultdict[str, defaultdict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    daily_project_skills: defaultdict[str, defaultdict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    project_messages: Counter[str] = Counter()
    project_sessions: defaultdict[str, set[str]] = defaultdict(set)
    project_skills: defaultdict[str, Counter[str]] = defaultdict(Counter)
    project_names: dict[str, str] = {}
    session_seen: set[str] = set()
    messages = 0
    files_used = 0
    known_lookup = {name.casefold(): name for name in skills}
    known_pattern = None
    if known_lookup:
        names = sorted((re.escape(name) for name in skills), key=len, reverse=True)
        known_pattern = re.compile(r"(?<![\w-])(" + "|".join(names) + r")(?![\w-])", re.I)

    for path in files:
        file_has_data = False
        current_session = path.stem
        current_project = "__unknown__"
        project_names.setdefault(current_project, "Unknown project")
        try:
            stream = path.open("r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with stream:
            for raw in stream:
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload") or {}
                if record.get("type") == "session_meta":
                    current_session = str(payload.get("session_id") or payload.get("id") or current_session)
                    cwd = payload.get("cwd")
                    if isinstance(cwd, str) and cwd.strip():
                        current_project = cwd.strip()
                        project_names[current_project] = Path(current_project).name or current_project
                timestamp = parse_time(record.get("timestamp") or payload.get("timestamp"))
                if timestamp is None or not (start <= timestamp <= end):
                    continue
                file_has_data = True
                session_id = current_session
                session_seen.add(session_id)
                day = iso_date(timestamp)
                daily_sessions[day].add(session_id)
                daily_project_sessions[day][current_project].add(session_id)
                project_sessions[current_project].add(session_id)
                if record.get("type") == "response_item":
                    role = payload.get("role")
                    if role in {"user", "assistant"}:
                        messages += 1
                        daily_messages[day] += 1
                        daily_project_messages[day][current_project] += 1
                        project_messages[current_project] += 1
                        for text in iter_message_text(record):
                            for skill in extract_mentions(text, known_lookup, known_pattern):
                                counts[skill] += 1
                                session_ids[skill].add(session_id)
                                daily_skills[day].add(skill)
                                daily_project_skills[day][current_project][skill] += 1
                                project_skills[current_project][skill] += 1
                                first_seen[skill] = min(first_seen.get(skill, timestamp), timestamp)
                                last_seen[skill] = max(last_seen.get(skill, timestamp), timestamp)
        if file_has_data:
            files_used += 1

    usage = []
    for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower())):
        usage.append(
            {
                "name": name,
                "mentions": count,
                "sessions": len(session_ids[name]),
                "first_seen": first_seen[name].isoformat().replace("+00:00", "Z"),
                "last_seen": last_seen[name].isoformat().replace("+00:00", "Z"),
            }
        )
    active_project_keys = sorted(
        (key for key in project_names if project_messages[key] or project_sessions[key]),
        key=lambda key: (-project_messages[key], project_names[key].lower(), key),
    )
    project_name_counts = Counter(project_names[key] for key in active_project_keys)
    project_ids = {
        key: "project-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        for key in active_project_keys
    }
    projects = []
    for key in active_project_keys:
        name = project_names[key]
        if key == "__unknown__":
            label = name
        elif project_name_counts[name] > 1:
            parent = Path(key).parent.name
            label = f"{parent}/{name}" if parent else name
        else:
            label = name
        projects.append(
            {
                "id": project_ids[key],
                "name": name,
                "label": label,
                "sessions": len(project_sessions[key]),
                "messages": project_messages[key],
                "skill_mentions": sum(project_skills[key].values()),
                "distinct_skills": len(project_skills[key]),
            }
        )

    days = []
    cursor = start.date()
    end_date = end.date()
    while cursor <= end_date:
        day = cursor.isoformat()
        project_breakdown = {}
        for key in active_project_keys:
            project_breakdown[project_ids[key]] = {
                "sessions": len(daily_project_sessions[day][key]),
                "messages": daily_project_messages[day][key],
                "skills": dict(sorted(daily_project_skills[day][key].items())),
            }
        days.append({
            "date": day,
            "sessions": len(daily_sessions[day]),
            "messages": daily_messages[day],
            "skills": len(daily_skills[day]),
            "projects": project_breakdown,
        })
        cursor += dt.timedelta(days=1)

    unused = sorted(name for name in skills if name not in counts)
    return {
        "period": {
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "label": f"{iso_date(start)}  ->  {iso_date(end)}",
        },
        "generated_at": dt.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "totals": {
            "sessions": len(session_seen),
            "messages": messages,
            "distinct_skills": len(usage),
            "available_skills": len(skills),
            "unused_skills": len(unused),
            "active_days": sum(1 for item in days if item["messages"]),
            "projects": len(projects),
        },
        "skill_usage": usage,
        "projects": projects,
        "unused_skills": unused,
        "timeline": days,
        "sources": {"files_scanned": len(files), "files_in_window": files_used},
    }


def default_roots() -> tuple[list[Path], list[Path]]:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    session_roots = [codex_home / "sessions", codex_home / "archived_sessions"]
    skill_roots = [
        codex_home / "skills",
        codex_home / "vendor_imports" / "skills" / "skills",
        Path.home() / ".agents" / "skills",
    ]
    plugin_root = codex_home / "plugins" / "cache"
    if plugin_root.exists():
        skill_roots.extend(path for path in plugin_root.glob("**/skills") if path.is_dir())
    return session_roots, skill_roots


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    session_defaults, skill_defaults = default_roots()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="Trailing calendar days (default: 7)")
    parser.add_argument("--start", help="Inclusive ISO timestamp/date (overrides --days)")
    parser.add_argument("--end", help="Inclusive ISO timestamp/date (default: now)")
    parser.add_argument("--sessions-root", action="append", type=Path, dest="session_roots", help="Session root; repeatable")
    parser.add_argument("--skills-root", action="append", type=Path, dest="skill_roots", help="Skill root; repeatable")
    parser.add_argument("--output", type=Path, default=Path("report.html"), help="HTML output path")
    parser.add_argument("--data-output", type=Path, help="Optional JSON data output path")
    parser.add_argument("--template", type=Path, help="HTML template override")
    args = parser.parse_args(argv)
    args.session_roots = [p.expanduser() for p in (args.session_roots or session_defaults)]
    args.skill_roots = [p.expanduser() for p in (args.skill_roots or skill_defaults)]
    now = dt.datetime.now(UTC)
    end = parse_time(args.end) if args.end else now
    if end is None:
        parser.error("--end must be an ISO date or timestamp")
    if args.start:
        start = parse_time(args.start)
    else:
        start = end - dt.timedelta(days=max(args.days, 1))
    if start is None or start > end:
        parser.error("--start must be an ISO date/timestamp before --end")
    args.start_dt, args.end_dt = start, end
    return args


def render(template: str, report: dict[str, Any], icon_data: str = "", data_url: str = "") -> str:
    data = json.dumps(report, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    marker = '<script type="application/json" id="report-data" data-source="__REPORT_DATA_URL__">__REPORT_DATA__</script>'
    legacy_marker = '<script type="application/json" id="report-data">__REPORT_DATA__</script>'
    if marker in template:
        rendered = template.replace(marker, f'<script type="application/json" id="report-data" data-source="{data_url}">{data}</script>')
    elif legacy_marker in template:
        rendered = template.replace(legacy_marker, f'<script type="application/json" id="report-data">{data}</script>')
    else:
        raise ValueError("template is missing the report-data marker")
    return rendered.replace("__CODEX_ICON_DATA__", icon_data)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    template_path = args.template or Path(__file__).resolve().parents[1] / "assets" / "report.html"
    if not template_path.exists():
        print(f"template not found: {template_path}", file=sys.stderr)
        return 2
    files = discover_log_files(args.session_roots, args.start_dt, args.end_dt)
    skills = discover_skills(args.skill_roots)
    report = analyze(files, skills, args.start_dt, args.end_dt)
    icon_path = Path(__file__).resolve().parents[1] / "assets" / "codex-icon.png"
    icon_data = ""
    if icon_path.exists():
        icon_data = "data:image/png;base64," + base64.b64encode(icon_path.read_bytes()).decode("ascii")
    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_url = ""
    if args.data_output:
        data_output = args.data_output.expanduser()
        data_output.parent.mkdir(parents=True, exist_ok=True)
        try:
            data_url = os.path.relpath(data_output, output.parent).replace(os.sep, "/")
        except ValueError:
            data_url = ""
    output.write_text(render(template_path.read_text(encoding="utf-8"), report, icon_data, data_url), encoding="utf-8")
    if args.data_output:
        data_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "totals": report["totals"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
