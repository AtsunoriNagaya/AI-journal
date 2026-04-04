from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.viewer.persona_reply_service import (
    PersonaReplyService,
    _error_status_code,
    _is_retryable_error,
    _load_openrouter_config,
)


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}


class _ErrorWithStatus(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status={status_code}")
        self.status_code = status_code


class _ErrorWithResponse(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"response={status_code}")
        self.response = _Response(status_code)


class PersonaReplyServiceTests(unittest.TestCase):
    def test_error_status_code_from_error_attr(self) -> None:
        error = _ErrorWithStatus(503)
        self.assertEqual(_error_status_code(error), 503)

    def test_error_status_code_from_response_attr(self) -> None:
        error = _ErrorWithResponse(429)
        self.assertEqual(_error_status_code(error), 429)

    def test_retryable_error_by_status_code(self) -> None:
        self.assertTrue(_is_retryable_error(_ErrorWithStatus(503)))
        self.assertFalse(_is_retryable_error(_ErrorWithStatus(400)))

    def test_retryable_error_by_message(self) -> None:
        timeout_error = RuntimeError("request timed out while calling upstream")
        bad_request_error = RuntimeError("bad request")
        self.assertTrue(_is_retryable_error(timeout_error))
        self.assertFalse(_is_retryable_error(bad_request_error))

    def test_persona_name_uses_first_non_empty_line(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            persona_path = Path(tmp_dir) / "persona.md"
            persona_path.write_text(
                "\n".join(
                    [
                        "# 日記ペルソナ",
                        "",
                        "## 主人公",
                        "23歳の新卒エンジニア",
                        "地方の国立大出身",
                        "",
                        "## 背景",
                        "2026年春。新人研修と実務立ち上がりが同時進行。",
                        "",
                        "## 期間",
                        "開始日 2026-04-01",
                        "7日間",
                    ]
                ),
                encoding="utf-8",
            )

            service = PersonaReplyService(persona_path)
            self.assertEqual(service.persona_name, "23歳の新卒エンジニア")

    def test_load_config_prefers_persona_retry_env(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "OPENROUTER_API_KEY": "dummy",
                "AI_JOURNAL_MAX_RETRIES": "7",
                "AI_PERSONA_MAX_RETRIES": "3",
            },
            clear=True,
        ):
            config = _load_openrouter_config(max_output_tokens_default=320)

        self.assertEqual(config.max_retries, 3)

    def test_load_config_falls_back_to_journal_retry_env(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "OPENROUTER_API_KEY": "dummy",
                "AI_JOURNAL_MAX_RETRIES": "4",
            },
            clear=True,
        ):
            config = _load_openrouter_config(max_output_tokens_default=320)

        self.assertEqual(config.max_retries, 4)


if __name__ == "__main__":
    unittest.main()
