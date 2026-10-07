"""Opt-in real-MySQL queue tests.

These never run against a normal development or production database. Enable
them only with GAMECUT_RUN_DB_INTEGRATION=1 and a database whose name ends in
`_test`, after applying the durable-job migration.
"""

import json
import os
import sys
import threading
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs import worker
from jobs.execution import JobOwnershipLostError
from utils.db import get_db_config, get_db_connection


RUN_LIVE = os.getenv("GAMECUT_RUN_DB_INTEGRATION") == "1"
DATABASE_NAME = get_db_config()["database"]


@unittest.skipUnless(RUN_LIVE, "Set GAMECUT_RUN_DB_INTEGRATION=1 to run real MySQL tests")
class LiveQueueConcurrencyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DATABASE_NAME.endswith("_test"):
            raise RuntimeError("Live integration tests require a database name ending in '_test'")

    def setUp(self):
        self.token = uuid.uuid4().hex
        self.project_id = None
        self.video_id = None
        self.job_id = None
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (f"queue-test-{self.token[:8]}", f"queue-{self.token}@example.invalid", "not-used"),
            )
            self.user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO projects (user_id, project_name, status) VALUES (%s, %s, 'draft')",
                (self.user_id, f"queue-test-{self.token}"),
            )
            self.project_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO videos
                    (project_id, user_id, original_filename, stored_filename, file_path, file_size, mime_type, status)
                VALUES (%s, %s, 'queue-test.mp4', 'queue-test.mp4', 'uploads/temp/queue-test.mp4', 1, 'video/mp4', 'uploaded')
                """,
                (self.project_id, self.user_id),
            )
            self.video_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO ai_jobs
                    (project_id, video_id, user_id, job_type, status, priority, payload, available_at)
                VALUES (%s, %s, %s, 'video_processing', 'queued', 127, %s, NOW())
                """,
                (self.project_id, self.video_id, self.user_id, json.dumps({"test": True})),
            )
            self.job_id = cursor.lastrowid
            connection.commit()
        finally:
            cursor.close()
            connection.close()

    def tearDown(self):
        if not self.project_id:
            return
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("DELETE FROM projects WHERE id = %s", (self.project_id,))
            connection.commit()
        finally:
            cursor.close()
            connection.close()

    def test_only_one_worker_claims_the_same_job(self):
        claimed = []
        failures = []
        start = threading.Barrier(2)

        def claim():
            try:
                start.wait(timeout=10)
                result = worker.claim_one_job()
                if result and result["id"] == self.job_id:
                    claimed.append(result)
            except Exception as exc:  # pragma: no cover - reported below
                failures.append(exc)

        threads = [threading.Thread(target=claim), threading.Thread(target=claim)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertFalse(failures, failures)
        self.assertEqual(len(claimed), 1)

    def test_cancelled_execution_cannot_publish_output(self):
        job = worker.claim_one_job()
        self.assertIsNotNone(job)
        self.assertEqual(job["id"], self.job_id)

        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("UPDATE ai_jobs SET status = 'cancelled' WHERE id = %s", (self.job_id,))
            connection.commit()
        finally:
            cursor.close()
            connection.close()

        with self.assertRaises(JobOwnershipLostError):
            worker.complete_rendering(job, "uploads/processed/should-not-publish.mp4", 1)

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT output_path, status FROM videos WHERE id = %s", (self.video_id,))
            video = cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

        self.assertIsNone(video["output_path"])
        self.assertEqual(video["status"], "processing")


if __name__ == "__main__":
    unittest.main()
