from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from web_ui import create_app


class WebUiApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = TemporaryDirectory()
        journals_dir = Path(self._temp_dir.name)

        (journals_dir / "2026-04-05.md").write_text("## 04/05\n今日は静かだった。", encoding="utf-8")
        (journals_dir / "2026-04-06.md").write_text("## 04/06\n通信障害への対応をした。", encoding="utf-8")
        (journals_dir / "2026-04-07.md").write_text("## 04/07\n会議の準備を整えた。", encoding="utf-8")

        app = create_app(journals_dir=journals_dir)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_home_page_renders(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("日記を、読み返しやすく。", response.text)

    def test_list_journals_api(self) -> None:
        response = self.client.get("/api/journals")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["items"][0]["date"], "2026-04-07")

    def test_detail_api_returns_prev_next(self) -> None:
        response = self.client.get("/api/journals/2026-04-06")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["previous_date"], "2026-04-05")
        self.assertEqual(payload["next_date"], "2026-04-07")
        self.assertIn("<p>", payload["html"])

    def test_search_query_filters_results(self) -> None:
        response = self.client.get("/api/journals", params={"q": "通信"})
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["date"], "2026-04-06")

    def test_invalid_date_returns_400(self) -> None:
        response = self.client.get("/api/journals/2026_04_07")
        self.assertEqual(response.status_code, 400)

    def test_missing_journal_returns_404(self) -> None:
        response = self.client.get("/api/journals/2026-04-20")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
