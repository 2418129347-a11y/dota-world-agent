from __future__ import annotations

import contextlib
import io
import json
import os
import smtplib
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agents/skills/dota-world-digest/scripts"))
from dota_news.cli import run
from dota_news.mailer import AmbiguousDeliveryError
from dota_news.workflow_ops import ALERT_MARKER, ALERT_TITLE, delivery_health, main, seconds_until_delivery, sync_alert


class WorkflowTests(unittest.TestCase):
    def test_early_ontime_delayed_afternoon_and_manual_clock(self):
        for timestamp, expected in [
            ("2026-10-06T07:43:00+08:00", 17 * 60),
            ("2026-10-06T08:00:00+08:00", 0),
            ("2026-10-06T11:20:00+08:00", 0),
            ("2026-10-06T16:19:00+08:00", 0),
            ("2026-10-06T23:59:59+08:00", 0),
        ]:
            with self.subTest(timestamp=timestamp):
                self.assertEqual(seconds_until_delivery(datetime.fromisoformat(timestamp), "schedule"), expected)
        early = datetime.fromisoformat("2026-10-06T07:43:00+08:00")
        self.assertEqual(seconds_until_delivery(early, "workflow_dispatch"), 0)
        self.assertEqual(seconds_until_delivery(early.astimezone(timezone.utc), "schedule"), 1020)
        # UTC Oct 5 is Beijing Oct 6; target is the new local day's 08:00.
        self.assertEqual(seconds_until_delivery(datetime.fromisoformat("2026-10-05T23:00:00+00:00"), "schedule"), 3600)

    def test_delivery_health_requires_real_evidence_and_enabled_sending(self):
        with tempfile.TemporaryDirectory() as temp:
            report, state = Path(temp) / "report.json", Path(temp) / "state.json"
            self.assertEqual(delivery_health(report, state, "true"), (False, "missing_or_invalid_delivery_report"))
            report.write_text(json.dumps({"delivery_date": "2026-10-06", "delivery": {"requested": True, "sent": True}}))
            self.assertEqual(delivery_health(report, state, "true"), (True, "sent"))
            self.assertEqual(delivery_health(report, state, "false"), (False, "sending_disabled"))
            report.write_text(json.dumps({"delivery_date": "2026-10-06", "delivery": {"sent": False, "reason": "already_sent_today"}}))
            state.write_text(json.dumps({"sent_dates": ["2026-10-05"]}))
            self.assertFalse(delivery_health(report, state, "true")[0])
            state.write_text(json.dumps({"sent_dates": ["2026-10-06"]}))
            self.assertEqual(delivery_health(report, state, "true"), (True, "already_sent_today_verified"))
            report.write_text(json.dumps({"delivery_date": "2026-10-06", "delivery": {"sent": False, "reason": "send_failed"}}))
            self.assertEqual(delivery_health(report, state, "true"), (False, "send_failed"))

    def test_plain_manual_run_and_next_trigger_share_actual_beijing_day(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = ["--fixture", str(ROOT / "tests/fixtures/sample_items.json"),
                    "--output-dir", str(root / "output"), "--state-file", str(root / "state.json"),
                    "--summarizer", "fallback", "--send", "--write-state", "--skip-if-sent-today"]
            clock = datetime.fromisoformat("2026-10-05T23:59:00+00:00")
            with patch("dota_news.cli.datetime", wraps=datetime) as dates, patch("dota_news.cli.send_email", return_value={"provider": "smtp"}) as send, contextlib.redirect_stdout(io.StringIO()):
                dates.now.return_value = clock
                self.assertEqual(run(args), 0)
                self.assertEqual(run(args), 0)
            self.assertEqual(send.call_count, 1)
            state = json.loads((root / "state.json").read_text())
            self.assertEqual(state["sent_dates"], ["2026-10-06"])
            report = json.loads((root / "output/report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["delivery_date"], "2026-10-06")
            self.assertEqual(report["delivery"]["reason"], "already_sent_today")

    def test_smtp_failure_writes_report_without_success_or_seen_items(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = ["--fixture", str(ROOT / "tests/fixtures/sample_items.json"),
                    "--output-dir", str(root / "output"), "--state-file", str(root / "state.json"),
                    "--date", "2026-08-17", "--send", "--write-state", "--summarizer", "fallback"]
            with patch("dota_news.cli.send_email", side_effect=smtplib.SMTPAuthenticationError(535, b"private credential details")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run(args), 1)
            state = json.loads((root / "state.json").read_text())
            self.assertEqual(state["sent_dates"], [])
            self.assertEqual(state["seen"], [])
            report_text = (root / "output/report.json").read_text(encoding="utf-8")
            self.assertNotIn("private credential", report_text)
            self.assertEqual(json.loads(report_text)["delivery"]["reason"], "send_failed")

    def test_ambiguous_transmission_blocks_later_heartbeat(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = ["--fixture", str(ROOT / "tests/fixtures/sample_items.json"),
                    "--output-dir", str(root / "output"), "--state-file", str(root / "state.json"),
                    "--date", "2026-08-17", "--send", "--write-state", "--summarizer", "fallback"]
            with patch("dota_news.cli.send_email", side_effect=AmbiguousDeliveryError()) as send, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run(args), 1)
                self.assertEqual(run(args), 1)
            self.assertEqual(send.call_count, 1)
            state = json.loads((root / "state.json").read_text())
            self.assertEqual(state["uncertain_dates"], ["2026-08-17"])
            self.assertEqual(state["sent_dates"], [])

    def test_alert_is_created_updated_and_closed_without_touching_user_issue(self):
        issues, calls = [], []
        def api(method, path, body=None):
            calls.append((method, path, body))
            if method == "GET":
                return issues
            if method == "POST" and path == "/issues":
                issues.append({"number": 7, "user": {"login": "github-actions[bot]"}, **body})
            return {}
        sync_alert(api, False, "send_failed", "https://github.com/example/repo/actions/runs/1")
        sync_alert(api, False, "send_failed", "https://github.com/example/repo/actions/runs/2")
        self.assertEqual(sum(m == "POST" and p == "/issues" for m, p, _ in calls), 1)
        self.assertTrue(any(m == "PATCH" and b and "body" in b for m, _, b in calls))
        issues.append({"number": 8, "title": ALERT_TITLE, "body": ALERT_MARKER, "user": {"login": "human"}})
        sync_alert(api, True, "sent", "https://github.com/example/repo/actions/runs/3")
        self.assertIn(("PATCH", "/issues/7", {"state": "closed"}), calls)
        self.assertFalse(any(p.startswith("/issues/8") for _, p, _ in calls))

    def test_notification_failure_does_not_change_original_delivery_status(self):
        env = {"GITHUB_REPOSITORY": "example/repo", "GITHUB_RUN_ID": "123",
               "DELIVERY_OK": "false", "DIGEST_RESULT": "failure", "GATE_RESULT": "success", "DELIVERY_REASON": "send_failed"}
        capture = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch("dota_news.workflow_ops.github_api", side_effect=OSError("private api details")), contextlib.redirect_stdout(capture):
            self.assertEqual(main(["notify"]), 1)
            self.assertEqual(os.environ["DIGEST_RESULT"], "failure")
        self.assertIn("original delivery result remains unchanged", capture.getvalue())
        self.assertNotIn("private api", capture.getvalue())

    def test_prior_job_failure_cannot_be_hidden_by_sent_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "output").mkdir()
            (root / "output/report.json").write_text(json.dumps({"delivery_date": "2026-10-06", "delivery": {"requested": True, "sent": True}}))
            old = os.getcwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"ENABLE_SEND": "true", "PRIOR_STATUS": "failure",
                     "GITHUB_OUTPUT": str(root / "step-output"), "GITHUB_STEP_SUMMARY": str(root / "step-summary")}), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["health"]), 1)
                self.assertIn("delivery_ok=false", (root / "step-output").read_text())
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
