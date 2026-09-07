import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.settings import router
from app.core.deps import get_current_user
from app.services import storage


class DirectoryBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="video-manage-folders-")
        self.root = Path(self.temp.name).resolve()
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_current_user] = lambda: object()
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.temp.cleanup()

    async def test_authentication_is_required_before_listing(self):
        self.app.dependency_overrides.clear()
        with patch("app.api.settings.browse_storage_directories") as browse:
            response = await self.client.get("/api/settings/directories")
            self.assertIn(response.status_code, (401, 403))
            browse.assert_not_called()

    async def test_roots_and_only_direct_children_are_returned(self):
        with patch.object(storage, "_directory_roots", return_value=[self.root]):
            response = await self.client.get("/api/settings/directories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["current_path"], "")
        self.assertIsNone(response.json()["parent_path"])
        self.assertEqual(response.json()["directories"][0]["path"], str(self.root))
        (self.root / "录像 文件夹").mkdir()
        (self.root / "archive").mkdir()
        (self.root / "archive" / "nested").mkdir()
        (self.root / "private.txt").write_text("must not be returned", encoding="utf-8")
        response = await self.client.get("/api/settings/directories", params={"path": str(self.root)})
        listing = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(listing["current_path"], str(self.root))
        self.assertEqual(listing["parent_path"], str(self.root.parent))
        self.assertEqual([entry["name"] for entry in listing["directories"]], ["archive", "录像 文件夹"])
        self.assertNotIn("must not be returned", response.text)

    async def test_relative_path_uses_the_same_root_as_storage(self):
        folder = self.root / "snapshots"
        folder.mkdir()
        with patch.object(storage, "_backend_root", return_value=self.root):
            response = await self.client.get("/api/settings/directories", params={"path": "./snapshots"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["current_path"], str(folder))
        self.assertEqual(response.json()["directories"], [])

    async def test_invalid_paths_and_permissions_are_reported(self):
        file = self.root / "file.txt"
        file.write_text("test", encoding="utf-8")
        for path, status in ((str(file), 400), (str(self.root / "missing"), 404), ("\x00", 400), ("x" * 513, 422)):
            with self.subTest(path=path):
                response = await self.client.get("/api/settings/directories", params={"path": path})
                self.assertEqual(response.status_code, status)
        with patch.object(storage.os, "scandir", side_effect=PermissionError):
            response = await self.client.get("/api/settings/directories", params={"path": str(self.root)})
            self.assertEqual(response.status_code, 403)
