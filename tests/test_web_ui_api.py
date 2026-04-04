from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from fastapi.testclient import TestClient

from web_ui import create_app


class _StubPersonaReplyService:
    persona_name = "23歳の新卒エンジニア"

    def generate_reply(self, **kwargs) -> str:
        return "コメントありがとう。明日はもう少し肩の力を抜いてやってみるよ。"


class _FailingPersonaReplyService:
    persona_name = "23歳の新卒エンジニア"

    def generate_reply(self, **kwargs) -> str:
        raise RuntimeError("boom")


class WebUiApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = TemporaryDirectory()
        journals_dir = Path(self._temp_dir.name)
        self.journals_dir = journals_dir

        (journals_dir / "2026-04-05.md").write_text("## 04/05\n今日は静かだった。", encoding="utf-8")
        (journals_dir / "2026-04-06.md").write_text("## 04/06\n通信障害への対応をした。", encoding="utf-8")
        (journals_dir / "2026-04-07.md").write_text("## 04/07\n会議の準備を整えた。", encoding="utf-8")

        app = create_app(
            journals_dir=journals_dir,
            persona_reply_service=_StubPersonaReplyService(),
        )
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
        self.assertIsInstance(payload["items"][0]["char_count"], int)

    def test_detail_api_returns_prev_next(self) -> None:
        response = self.client.get("/api/journals/2026-04-06")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["previous_date"], "2026-04-05")
        self.assertEqual(payload["next_date"], "2026-04-07")
        self.assertIn("<p>", payload["html"])
        self.assertEqual(payload["comment_count"], 0)

    def test_post_comment_and_reflect_in_html_and_api(self) -> None:
        response = self.client.post(
            "/comments/2026-04-07",
            data={"author": "テスト太郎", "body": "これはコメントです"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        location = response.headers["location"]
        self.assertIn("comment_saved=1", location)

        page = self.client.get(location)
        self.assertEqual(page.status_code, 200)
        self.assertIn("コメントを保存しました。", page.text)
        self.assertIn("これはコメントです", page.text)
        self.assertIn("コメントありがとう。明日はもう少し肩の力を抜いてやってみるよ。", page.text)

        detail = self.client.get("/api/journals/2026-04-07")
        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        self.assertEqual(payload["comment_count"], 2)
        self.assertEqual(payload["comments"][0]["author"], "テスト太郎")
        self.assertEqual(payload["comments"][0]["role"], "user")
        self.assertEqual(payload["comments"][0]["body"], "これはコメントです")
        self.assertEqual(payload["comments"][1]["author"], "23歳の新卒エンジニア")
        self.assertEqual(payload["comments"][1]["role"], "persona")

    def test_post_comment_preserves_search_query_in_redirect(self) -> None:
        response = self.client.post(
            "/comments/2026-04-07",
            data={"author": "テスト", "body": "検索付きコメント", "q": "通信"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

        location = response.headers["location"]
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        self.assertEqual(params.get("q"), ["通信"])

    def test_post_empty_comment_returns_error_message(self) -> None:
        response = self.client.post(
            "/comments/2026-04-07",
            data={"author": "", "body": "   "},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        location = response.headers["location"]
        self.assertIn("comment_error=", location)

        page = self.client.get(location)
        self.assertEqual(page.status_code, 200)
        self.assertIn("コメント本文を入力してください", page.text)

    def test_invalid_comment_skips_reply_history_lookup(self) -> None:
        app = create_app(
            journals_dir=self.journals_dir,
            persona_reply_service=_StubPersonaReplyService(),
        )
        client = TestClient(app)
        comment_repository = app.state.comment_repository

        with patch.object(
            comment_repository,
            "list_comments",
            wraps=comment_repository.list_comments,
        ) as mocked_list_comments:
            response = client.post(
                "/comments/2026-04-07",
                data={"author": "", "body": "   "},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(mocked_list_comments.call_count, 0)

    def test_reply_generation_failure_keeps_user_comment(self) -> None:
        app = create_app(
            journals_dir=self.journals_dir,
            persona_reply_service=_FailingPersonaReplyService(),
        )
        client = TestClient(app)

        response = client.post(
            "/comments/2026-04-07",
            data={"author": "テスト", "body": "返信どうなる?"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        location = response.headers["location"]

        page = client.get(location)
        self.assertEqual(page.status_code, 200)
        self.assertIn("コメントは保存しましたが、ペルソナ返信の生成に失敗しました。", page.text)

        detail = client.get("/api/journals/2026-04-07")
        payload = detail.json()
        self.assertEqual(payload["comment_count"], 1)
        self.assertEqual(payload["comments"][0]["role"], "user")

    def test_comments_reset_after_app_restart(self) -> None:
        response = self.client.post(
            "/comments/2026-04-07",
            data={"author": "A", "body": "テスト"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

        app_after_restart = create_app(
            journals_dir=self.journals_dir,
            persona_reply_service=_StubPersonaReplyService(),
        )
        client_after_restart = TestClient(app_after_restart)

        detail = client_after_restart.get("/api/journals/2026-04-07")
        payload = detail.json()
        self.assertEqual(payload["comment_count"], 0)

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
