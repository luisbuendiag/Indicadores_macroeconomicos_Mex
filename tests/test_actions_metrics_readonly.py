import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

from scripts.audit_actions_metrics import collect, summarize_runs

NOW = datetime(2026, 11, 16, 19, tzinfo=timezone.utc)
WORKFLOW = ".github/workflows/update-data.yml"


def run(rid, conclusion="success", attempt=1):
    return {"id": rid, "path": WORKFLOW, "status": "completed",
            "conclusion": conclusion, "run_attempt": attempt,
            "updated_at": NOW.isoformat()}


def job(seconds=40):
    return {"status": "completed",
            "started_at": (NOW-timedelta(seconds=seconds)).isoformat(),
            "completed_at": NOW.isoformat()}


class ActionsMetricsTests(unittest.TestCase):
    def test_counts_failures_and_attempts(self):
        r = summarize_runs([run(1), run(2, "failure", 3)],
                           {1: [job(25)], 2: [job(15), job(10)]})
        self.assertEqual((r["runs_count"], r["failed_runs"], r["retry_attempts"]), (2, 1, 2))
        self.assertEqual(r["total_job_compute_seconds"], 50)

    def test_incomplete_runs_not_marked_success(self):
        self.assertEqual(summarize_runs([
            {**run(1), "status": "in_progress"},
            {**run(2), "conclusion": None}
        ], {})["runs_count"], 0)

    def test_foreign_workflows_not_collected(self):
        self.assertEqual(summarize_runs([
            {**run(1), "path": ".github/workflows/other.yml"}
        ], {})["runs_count"], 0)

    def test_missing_jobs_fail_closed(self):
        with self.assertRaises(ValueError):
            summarize_runs([run(1)], {})
        with self.assertRaises(ValueError):
            summarize_runs([run(1)], {1: []})

    def test_reject_truncated_job_api(self):
        with patch("scripts.audit_actions_metrics.api_read",
                   side_effect=[{"workflow_runs": [run(1)]},
                                {"total_count": 2, "jobs": [job()]}]):
            with self.assertRaises(ValueError):
                collect("test_only", limit=1)

    def test_collection_only_reads_allowed_routes(self):
        seen = []
        def fake(path, *, token):
            seen.append(path)
            if path.endswith("/actions/runs?per_page=30"):
                return {"workflow_runs": [run(1)]}
            if path.endswith("/actions/runs/1/jobs?per_page=100"):
                return {"total_count": 1, "jobs": [job()]}
            raise AssertionError("unsafe route")
        with patch("scripts.audit_actions_metrics.api_read", side_effect=fake):
            result = collect("test_only", limit=1)
        self.assertEqual(result["runs_count"], 1)
        self.assertEqual(len(seen), 2)
        self.assertTrue(all("/actions/" in x for x in seen))

    def test_never_copy_job_logs(self):
        row = {**job(), "name": "private_user_details",
               "steps": [{"name": "secret"}]}
        text = str(summarize_runs([run(1)], {1: [row]}))
        self.assertNotIn("private_user_details", text)
        self.assertNotIn("secret", text)


if __name__ == "__main__":
    unittest.main()
