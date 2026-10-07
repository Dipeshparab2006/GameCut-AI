import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.execution import (
    EXECUTION_TOKEN_KEY,
    RUNTIME_KEY,
    attach_execution_token,
    execution_token_for,
    execution_work_directory,
    new_execution_token,
    payload_as_dict,
)


class JobExecutionTestCase(unittest.TestCase):
    def test_attaching_token_preserves_user_payload_and_replaces_runtime_token(self):
        original = {
            "style": "Esports",
            RUNTIME_KEY: {EXECUTION_TOKEN_KEY: "user-controlled-value", "other": "kept"},
        }

        payload = attach_execution_token(original, "a" * 24)

        self.assertEqual(payload["style"], "Esports")
        self.assertEqual(payload[RUNTIME_KEY]["other"], "kept")
        self.assertEqual(payload[RUNTIME_KEY][EXECUTION_TOKEN_KEY], "a" * 24)
        self.assertEqual(original[RUNTIME_KEY][EXECUTION_TOKEN_KEY], "user-controlled-value")

    def test_payload_parser_accepts_json_object_and_rejects_non_object_values(self):
        self.assertEqual(payload_as_dict(json.dumps({"game": "Valorant"})), {"game": "Valorant"})
        self.assertEqual(payload_as_dict("[]"), {})
        self.assertEqual(payload_as_dict("not-json"), {})

    def test_execution_token_can_be_read_from_claimed_job(self):
        payload = attach_execution_token({"target_duration": 45}, "b" * 24)
        self.assertEqual(execution_token_for({"payload": payload}), "b" * 24)
        self.assertEqual(execution_token_for({"payload": {}, "execution_token": "c" * 24}), "c" * 24)

    def test_workspaces_are_isolated_and_stay_under_the_analysis_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = execution_work_directory(root, 42, "d" * 24)
            second = execution_work_directory(root, 42, "e" * 24)

        self.assertNotEqual(first, second)
        self.assertEqual(first.parent.parent, root.resolve())

    def test_generated_token_is_filesystem_safe(self):
        token = new_execution_token()
        self.assertEqual(execution_token_for({"execution_token": token}), token)


if __name__ == "__main__":
    unittest.main()
