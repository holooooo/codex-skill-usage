import json
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "codex-usage-insights" / "scripts" / "codex_usage_report.py"
SPEC = importlib.util.spec_from_file_location("codex_usage_report", SCRIPT)
report = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = report
SPEC.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def test_analyze_counts_explicit_mentions_and_excludes_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log = root / "rollout.jsonl"
            records = [
                {"timestamp": "2026-08-05T10:00:00Z", "type": "session_meta", "payload": {"session_id": "s1", "cwd": "/work/demo-project", "base_instructions": "$unused-skill $gsap-core"}},
                {"timestamp": "2026-08-05T10:01:00Z", "type": "response_item", "payload": {"role": "user", "content": [{"type": "input_text", "text": "Use $gsap-core for this report"}]}},
                {"timestamp": "2026-08-05T10:02:00Z", "type": "response_item", "payload": {"role": "assistant", "content": [{"type": "output_text", "text": "Using gsap-core."}]}},
                {"timestamp": "2026-08-06T10:00:00Z", "type": "response_item", "payload": {"role": "tool", "content": [{"type": "output_text", "text": "$unused-skill"}]}},
            ]
            log.write_text("\n".join(json.dumps(item) for item in records), encoding="utf-8")
            start = datetime(2026, 8, 5, tzinfo=timezone.utc)
            end = datetime(2026, 8, 7, tzinfo=timezone.utc)
            result = report.analyze([log], {"gsap-core": log, "unused-skill": log}, start, end)
            self.assertEqual(result["totals"]["messages"], 2)
            self.assertEqual(result["skill_usage"][0]["name"], "gsap-core")
            self.assertEqual(result["skill_usage"][0]["mentions"], 2)
            self.assertEqual(result["unused_skills"], ["unused-skill"])
            self.assertEqual(result["totals"]["projects"], 1)
            self.assertEqual(result["projects"][0]["name"], "demo-project")
            project_id = result["projects"][0]["id"]
            self.assertEqual(result["timeline"][0]["projects"][project_id]["messages"], 2)
            self.assertEqual(result["timeline"][0]["projects"][project_id]["skills"]["gsap-core"], 2)

    def test_render_embeds_report_data_and_icon(self):
        template = '<img src="__CODEX_ICON_DATA__"><script type="application/json" id="report-data" data-source="__REPORT_DATA_URL__">__REPORT_DATA__</script>'
        rendered = report.render(template, {"value": "</script>"}, "data:image/png;base64,abc", "report-data.json")
        self.assertIn("data:image/png;base64,abc", rendered)
        self.assertIn("<\\/script>", rendered)
        self.assertIn('data-source="report-data.json"', rendered)


if __name__ == "__main__":
    unittest.main()
