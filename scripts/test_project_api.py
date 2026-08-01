"""Smoke tests for file-explorer folder operations."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module


class ProjectApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = app_module.DB_PATH
        app_module.DB_PATH = Path(self.temp_dir.name) / "test.db"
        app_module.init_db()
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_deleted_folder_disappears_from_fresh_history(self):
        created = self.client.post("/projects", json={"name": "Delete me"})
        self.assertEqual(created.status_code, 200)
        project_id = created.get_json()["project"]["id"]

        before_delete = self.client.get("/history")
        self.assertEqual(before_delete.headers["Cache-Control"], "no-store, max-age=0")
        self.assertIn(project_id, [item["id"] for item in before_delete.get_json()["projects"]])

        deleted = self.client.delete(f"/projects/{project_id}?mode=keep_files")
        self.assertEqual(deleted.status_code, 200)

        after_delete = self.client.get("/history")
        self.assertNotIn(project_id, [item["id"] for item in after_delete.get_json()["projects"]])


if __name__ == "__main__":
    unittest.main()
