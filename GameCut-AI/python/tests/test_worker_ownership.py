import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs import worker
from jobs.execution import JobOwnershipLostError, attach_execution_token


class FakeCursor:
    def __init__(self, rowcount=1):
        self.rowcount = rowcount
        self.executed = []
        self.closed = False

    def execute(self, statement, params=None):
        self.executed.append((statement, params))

    def close(self):
        self.closed = True

    def fetchone(self):
        return (0,)


class FakeConnection:
    def __init__(self, rowcount=1):
        self.cursor_instance = FakeCursor(rowcount)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class RecoveryCursor(FakeCursor):
    def __init__(self, exhausted_jobs=None, active_jobs=0):
        super().__init__(rowcount=0)
        self.exhausted_jobs = exhausted_jobs or []
        self.active_jobs = active_jobs

    def execute(self, statement, params=None):
        super().execute(statement, params)
        if "SET status = 'queued'" in statement:
            self.rowcount = 1
        elif "SET status = 'failed'" in statement:
            self.rowcount = 1

    def fetchall(self):
        return list(self.exhausted_jobs)

    def fetchone(self):
        return {"active_jobs": self.active_jobs}


class RecoveryConnection(FakeConnection):
    def __init__(self, exhausted_jobs=None, active_jobs=0):
        super().__init__()
        self.cursor_instance = RecoveryCursor(exhausted_jobs, active_jobs)


def claimed_job():
    payload = attach_execution_token({"style": "Esports"}, "f" * 24)
    return {
        "id": 7,
        "project_id": 3,
        "video_id": 5,
        "payload": payload,
        "execution_token": "f" * 24,
    }


class WorkerOwnershipTestCase(unittest.TestCase):
    def test_progress_update_rejects_a_stale_execution(self):
        connection = FakeConnection(rowcount=0)
        with patch.object(worker, "get_db_connection", return_value=connection):
            with self.assertRaises(JobOwnershipLostError):
                worker.update_job(claimed_job(), 20, "rendering")

        statement, params = connection.cursor_instance.executed[0]
        self.assertIn("execution_token", statement)
        self.assertEqual(params[-1], "f" * 24)
        self.assertGreaterEqual(connection.rollbacks, 1)

    def test_stale_execution_cannot_publish_related_video_state(self):
        connection = FakeConnection(rowcount=0)
        with patch.object(worker, "get_db_connection", return_value=connection), patch.object(
            worker, "_set_related_completed"
        ) as related:
            with self.assertRaises(JobOwnershipLostError):
                worker.complete_rendering(claimed_job(), "uploads/processed/run.mp4", 12.5)

        related.assert_not_called()
        self.assertGreaterEqual(connection.rollbacks, 1)

    def test_stale_execution_cannot_mark_project_failed(self):
        connection = FakeConnection(rowcount=0)
        with patch.object(worker, "get_db_connection", return_value=connection), patch.object(
            worker, "_set_related_failed"
        ) as related:
            recorded = worker.fail_job(claimed_job(), "renderer failed")

        self.assertFalse(recorded)
        related.assert_not_called()

    def test_current_execution_commits_and_updates_related_state(self):
        connection = FakeConnection(rowcount=1)
        job = claimed_job()
        with patch.object(worker, "get_db_connection", return_value=connection), patch.object(
            worker, "_set_related_completed"
        ) as related:
            worker.complete_rendering(job, "uploads/processed/run.mp4", 12.5)

        related.assert_called_once_with(connection.cursor_instance, 3, 5, "uploads/processed/run.mp4", 12.5)
        self.assertEqual(connection.commits, 1)

    def test_exhausted_stale_job_becomes_terminal_instead_of_stuck_processing(self):
        connection = RecoveryConnection(exhausted_jobs=[{"id": 7, "project_id": 3, "video_id": 5}])
        with patch.object(worker, "get_db_connection", return_value=connection), patch.object(
            worker, "_set_related_failed"
        ) as related:
            recovered = worker.recover_stale_jobs()

        self.assertEqual(recovered, 1)
        related.assert_called_once_with(connection.cursor_instance, 3, 5)
        self.assertEqual(connection.commits, 1)

    def test_failed_execution_removes_unpublished_output_and_render_intermediates(self):
        with patch.object(worker, "cleanup_unpublished_output") as output_cleanup, patch.object(
            worker, "cleanup_job_temp_files"
        ) as temp_cleanup:
            worker.cleanup_failed_execution("work-dir", "output.mp4", published=False)

        output_cleanup.assert_called_once_with("output.mp4")
        temp_cleanup.assert_called_once_with("work-dir")

    def test_failed_cleanup_never_deletes_an_output_after_publication(self):
        with patch.object(worker, "cleanup_unpublished_output") as output_cleanup, patch.object(
            worker, "cleanup_job_temp_files"
        ) as temp_cleanup:
            worker.cleanup_failed_execution("work-dir", "output.mp4", published=True)

        output_cleanup.assert_not_called()
        temp_cleanup.assert_called_once_with("work-dir")

    def test_retryable_error_is_requeued_before_max_attempts(self):
        job = claimed_job()
        job.update({"attempts": 1, "max_attempts": 3})
        with patch.object(worker, "retry_job", return_value=True) as retry, patch.object(
            worker, "fail_job"
        ) as fail:
            outcome = worker.retry_or_fail_job(job, RuntimeError("FFmpeg process interrupted"))

        self.assertTrue(outcome)
        retry.assert_called_once()
        fail.assert_not_called()

    def test_invalid_input_is_terminal_without_retry(self):
        job = claimed_job()
        job.update({"attempts": 1, "max_attempts": 3})
        with patch.object(worker, "retry_job") as retry, patch.object(worker, "fail_job", return_value=True) as fail:
            outcome = worker.retry_or_fail_job(job, ValueError("Unsupported video file type"))

        self.assertTrue(outcome)
        retry.assert_not_called()
        fail.assert_called_once()

    def test_exhausted_attempts_are_terminal(self):
        job = claimed_job()
        job.update({"attempts": 3, "max_attempts": 3})
        with patch.object(worker, "retry_job") as retry, patch.object(worker, "fail_job", return_value=True) as fail:
            outcome = worker.retry_or_fail_job(job, RuntimeError("FFmpeg process interrupted"))

        self.assertTrue(outcome)
        retry.assert_not_called()
        fail.assert_called_once()

    def test_retry_backoff_is_bounded(self):
        self.assertEqual(worker.retry_delay_seconds(1), 15)
        self.assertEqual(worker.retry_delay_seconds(2), 30)
        self.assertEqual(worker.retry_delay_seconds(99), 900)


if __name__ == "__main__":
    unittest.main()
