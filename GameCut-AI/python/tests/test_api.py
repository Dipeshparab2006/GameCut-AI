import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ApiTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env_patch = patch.dict(os.environ, {"GAMECUT_AI_API_TOKEN": "test-token"})
        self.env_patch.start()

        self.deps_patch = patch(
            "api.routes.dependency_status",
            return_value={"mysql_connector": True, "database": True},
        )
        self.status_patch = patch(
            "api.routes.fetch_job_status",
            side_effect=lambda job_id: {
                "id": job_id,
                "status": "processing",
                "progress": 50,
                "current_step": "processing",
                "error_message": None,
                "updated_at": None,
            },
        )
        self.deps_patch.start()
        self.status_patch.start()

        from app import app

        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.status_patch.stop()
        self.deps_patch.stop()
        self.env_patch.stop()

    def auth_headers(self):
        return {"X-GameCut-Token": os.environ["GAMECUT_AI_API_TOKEN"]}

    async def test_health_success(self):
        response = await self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(response.json()["dependencies"]["database"])

    async def test_valid_job_request(self):
        response = await self.client.post("/jobs/123", headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"success": True, "job_id": 123, "status": "received"},
        )

    async def test_invalid_job_id(self):
        response = await self.client.post("/jobs/0", headers=self.auth_headers())
        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json()["success"])

    async def test_unauthorized_request(self):
        response = await self.client.post("/jobs/123")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["error"], "Unauthorized")

    async def test_malformed_request(self):
        response = await self.client.get("/jobs/not-a-number/status", headers=self.auth_headers())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "Validation failed")

    async def test_job_status_success(self):
        response = await self.client.get("/jobs/123/status", headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["progress"], 50)


if __name__ == "__main__":
    unittest.main()
