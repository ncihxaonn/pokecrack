from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("global_research", ROOT / "scripts/global_research.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GlobalResearchTests(unittest.TestCase):
    def batch(self):
        row = json.loads((ROOT / "data/research/global-studies.json").read_text())["studies"][0]
        return module.validate_batch(json.dumps({"version": 1, "studies": [row]}).encode())

    def test_focus_rotation_is_worldwide(self):
        start = datetime(2026, 9, 8, tzinfo=timezone.utc)
        self.assertEqual([module.select_scope("auto", start + timedelta(hours=6*i))
                          for i in range(7)], list(module.SCOPES))
        self.assertEqual(module.select_scope("auto", start + timedelta(hours=42)), "global")

    def test_research_results_never_self_approve(self):
        row = self.batch()["studies"][0]
        self.assertIn("independent-review-pending", row["limitations"])
        self.assertIn("collector-policy-not-enabled", row["limitations"])
        self.assertIsNone(row["country"])

    def test_batch_limit(self):
        batch = self.batch()
        batch["studies"] *= 7
        with self.assertRaises(ValueError):
            module.validate_batch(json.dumps(batch).encode())

    def test_normalized_batch_must_fit_future_history_reader(self):
        batch = self.batch()
        batch["studies"][0]["limitations"] = []
        raw = json.dumps(batch).encode()
        with patch.object(module, "MAX_BYTES", len(raw) + 1):
            with self.assertRaises(ValueError):
                module.validate_batch(raw)

    def test_history_round_trip_and_bot_only(self):
        batch = self.batch()
        item = {"title": module.TITLE + module.fingerprint(batch),
                "body": module.issue_body(batch),
                "author": {"login": "app/github-actions", "is_bot": True}}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([item]))):
            self.assertEqual(module.load_history(), batch["studies"])
        item["author"] = {"login": "ncihxaonn", "is_bot": False}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([item]))):
            self.assertEqual(module.load_history(), [])

    def test_legacy_history_fingerprint_survives_native_sample_extension(self):
        batch = self.batch()
        batch["studies"][0].pop("source_sample", None)
        digest = module.fingerprint(batch)
        item = {"title": module.TITLE + digest, "body": module.issue_body(batch),
                "author": {"login": "app/github-actions", "is_bot": True}}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([item]))):
            self.assertEqual(module.load_history(), batch["studies"])
        self.assertEqual(module.fingerprint(module.validate_batch(json.dumps(batch).encode())), digest)

    def test_new_schema_and_prompt_preserve_native_units(self):
        fields = module.schema()["properties"]["studies"]["items"]
        self.assertIn("source_sample", fields["required"])
        self.assertEqual(fields["properties"]["source_sample"]["properties"]["unit"]["enum"],
                         ["boxes", "cartons", "decks"])
        self.assertIn("Never multiply box contents into packs", module.prompt("asia"))

    def test_tampered_history_fails_closed(self):
        item = {"title": module.TITLE + "wrong", "body": module.issue_body(self.batch()),
                "author": {"login": "app/github-actions", "is_bot": True}}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([item]))):
            with self.assertRaises(ValueError):
                module.load_history()

    def test_accumulation_retains_old_reports_and_skips_exact_replays(self):
        batch = self.batch()
        new, ledger = module.accumulate(batch, {"studies": []}, batch["studies"])
        self.assertEqual(new["studies"], [])
        self.assertEqual(ledger["distinct_report_groups"], 1)
        self.assertIsNone(ledger["verified_unique_packs"])

    def test_history_at_capacity_does_not_silently_truncate(self):
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([{}]*1000))):
            with self.assertRaises(ValueError):
                module.load_history()

    def test_no_rewrite_for_unchanged_batch(self):
        batch = self.batch()
        with patch.object(module, "load_history", return_value=batch["studies"]), \
                patch.object(module.subprocess, "run") as run:
            module.publish(batch, ROOT / "data/research/global-studies.json")
            run.assert_not_called()

    def test_workflow_is_main_only_and_has_no_production_db_credentials(self):
        workflow = (ROOT / ".github/workflows/global-research.yml").read_text()
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("global-ledger.json", workflow)
        self.assertNotIn("SUPABASE", workflow)
        self.assertNotIn("OPENAI_API_KEY", workflow)
        legacy = (ROOT / ".github/workflows/asia-research.yml").read_text()
        self.assertNotIn("cron:", legacy)

    def test_failure_codes_do_not_expose_exception_payloads(self):
        private = "https://example.com/?token=secret /private/auth.json"
        errors = [ValueError(private), TypeError(private), KeyError(private),
                  OSError(private), json.JSONDecodeError(private, private, 0),
                  subprocess.CalledProcessError(1, private, output=private, stderr=private)]
        self.assertEqual([module.failure_code(error) for error in errors],
                         ["invalid_input", "invalid_input", "invalid_input",
                          "io_unavailable", "invalid_json", "provider_command_failed"])
        for code in module.SAFE_FAILURE_CODES:
            self.assertEqual(module.failure_code(ValueError(code)), code)

    def test_research_failure_has_safe_stage_and_no_report_output(self):
        for code in ("research_timeout", "research_unavailable"):
            with self.subTest(code=code), patch.object(sys, "argv", ["global_research.py"]), \
                    patch.object(module, "research_document", side_effect=ValueError(code)), \
                    patch.object(module, "publish") as publish, redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as caught:
                    module.main()
                self.assertEqual(str(caught.exception),
                    f"global_research_failed: stage=research code={code}; no production data admitted")
                self.assertEqual(output.getvalue(), "")
                publish.assert_not_called()

    def test_invalid_generated_batch_is_rejected_not_repaired(self):
        batch = self.batch()
        batch["studies"][0]["pack_precision"] = "private-error-payload"
        with patch.object(sys, "argv", ["global_research.py"]), \
                patch.object(module, "research_document", return_value=json.dumps(batch).encode()), \
                patch.object(module, "publish") as publish, redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as caught:
                module.main()
            self.assertEqual(str(caught.exception),
                "global_research_failed: stage=validation code=invalid_pack_precision; no production data admitted")
            self.assertEqual(output.getvalue(), "")
            publish.assert_not_called()

    def test_invalid_json_does_not_expose_document_or_traceback(self):
        with patch.object(sys, "argv", ["global_research.py"]), \
                patch.object(module, "research_document", return_value=b'private-invalid-json'), \
                redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as caught:
                module.main()
            self.assertEqual(str(caught.exception),
                "global_research_failed: stage=validation code=invalid_json; no production data admitted")
            self.assertEqual(output.getvalue(), "")
            self.assertTrue(caught.exception.__suppress_context__)

    def test_missing_batch_and_history_failure_have_distinct_stages(self):
        with patch.object(sys, "argv", ["global_research.py", "--publish", "private-path"]), \
                patch.object(Path, "open", side_effect=FileNotFoundError("private-path")):
            with self.assertRaises(SystemExit) as caught:
                module.main()
            self.assertIn("stage=read_batch code=io_unavailable;", str(caught.exception))
        with patch.object(sys, "argv", ["global_research.py", "--publish", "private-path"]), \
                patch.object(Path, "open", return_value=io.BytesIO(json.dumps(self.batch()).encode())), \
                patch.object(module, "publish", side_effect=ValueError("history_fingerprint_mismatch")), \
                redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as caught:
                module.main()
            self.assertIn("stage=publication code=history_fingerprint_mismatch;", str(caught.exception))
            self.assertEqual(output.getvalue(), "")

    def test_successful_research_output_keeps_canonical_batch(self):
        batch = self.batch()
        with patch.object(sys, "argv", ["global_research.py", "--scope", "oceania"]), \
                patch.object(module, "research_document", return_value=json.dumps(batch).encode()), \
                redirect_stdout(io.StringIO()) as output:
            module.main()
            self.assertEqual(json.loads(output.getvalue()), batch)


if __name__ == "__main__":
    unittest.main()
