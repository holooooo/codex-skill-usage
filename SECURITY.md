# Security Policy

## Scope

`codex-usage-insights` is local-first. Its bundled script reads Codex session JSONL files and installed skill metadata from paths supplied by the user, then writes the report files to an output path chosen by the user.

The project does not upload session logs, call remote services, or execute commands discovered in log content.

## Reporting a Vulnerability

Please report security issues privately through [GitHub's private vulnerability reporting](https://github.com/holooooo/codex-skill-usage/security/advisories/new). Include the affected file, reproduction steps, and impact. Do not include personal session logs; synthetic examples are sufficient.
