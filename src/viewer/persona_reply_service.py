"""コメントに対するペルソナ返信の生成サービス。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
import time

from src.input.character_setting import JournalSetting, load_setting_from_markdown
from src.viewer.comment_repository import JournalComment
from src.utils.env_utils import read_int_env


@dataclass(frozen=True)
class _OpenRouterConfig:
    """返信生成で使う OpenRouter 設定。"""

    api_key: str
    model: str
    max_retries: int
    max_output_tokens: int
    site_url: str
    site_name: str


class PersonaReplyService:
    """ユーザーコメントに対するペルソナ返信を生成する。"""

    def __init__(self, persona_path: Path) -> None:
        self._persona_path = persona_path
        self._setting_cache: JournalSetting | None = None

    @property
    def persona_name(self) -> str:
        # UI上は長文ロールをそのまま出さず、先頭行を表示名として使う。
        for line in self._setting.role.splitlines():
            candidate = line.strip()
            if candidate:
                return candidate
        return "ペルソナ"

    @property
    def persona_background(self) -> str:
        return self._setting.background

    @property
    def persona_tone_keywords(self) -> str:
        return self._setting.tone_keywords

    def generate_reply(
        self,
        *,
        journal_date: date,
        journal_text: str,
        user_comment: str,
        recent_comments: list[JournalComment],
    ) -> str:
        # 返信は短文が前提なので、日記本文より低めの token 既定値を使う。
        config = _load_openrouter_config(max_output_tokens_default=320)

        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate
        except ImportError as exc:
            raise RuntimeError("langchain / langchain-openai is not installed") from exc

        setting = self._setting
        # system で人物像を固定し、human で当日の文脈を渡す。
        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", _build_system_prompt(setting)),
                (
                    "human",
                    _build_user_prompt(
                        journal_date=journal_date,
                        journal_text=journal_text,
                        user_comment=user_comment,
                        recent_comments=recent_comments,
                    ),
                ),
            ]
        )

        last_error: Exception | None = None
        for retry in range(config.max_retries + 1):
            try:
                llm = _create_llm(config)
                chain = prompt_template | llm | StrOutputParser()
                reply = chain.invoke({}).strip()
                if not reply:
                    raise RuntimeError("empty reply")
                return reply
            except Exception as exc:
                last_error = exc
                if not _is_retryable_error(exc):
                    raise RuntimeError("ペルソナ返信の生成に失敗しました") from exc
                if retry < config.max_retries:
                    # retry-after ヘッダーがあれば尊重し、なければ指数バックオフ。
                    time.sleep(_retry_delay_seconds(exc, retry))
                    continue

        raise RuntimeError("ペルソナ返信の生成に失敗しました") from last_error

    @property
    def _setting(self) -> JournalSetting:
        # persona.md の再読込を避けるため、初回だけ読み込んでキャッシュする。
        if self._setting_cache is None:
            self._setting_cache = load_setting_from_markdown(str(self._persona_path))
        return self._setting_cache


def _build_system_prompt(setting: JournalSetting) -> str:
    """返信スタイルを固定する system prompt を構築する。"""
    return (
        "あなたは以下の人物として返信してください。\n"
        f"- 主人公: {setting.role}\n"
        f"- 背景: {setting.background}\n"
        f"- 文体: {setting.tone_keywords}\n"
        f"- 現実味の制約: {setting.realism_constraints}\n"
        "\n"
        "返信ルール:\n"
        "- 日本語で、親しみやすく自然に返信する\n"
        "- 1〜3文、全体で120文字前後に収める\n"
        "- 説教調・断定調を避ける\n"
        "- 相手のコメント内容に具体的に触れる\n"
        "- 不明点がある場合は1つだけ短く質問して終える\n"
        "- 返信本文のみを出力する"
    )


def _build_user_prompt(
    *,
    journal_date: date,
    journal_text: str,
    user_comment: str,
    recent_comments: list[JournalComment],
) -> str:
    """当日の文脈と会話履歴を含む user prompt を構築する。"""
    history_lines: list[str] = []
    for item in recent_comments[-6:]:
        # 役割を明示して渡すことで、モデルが口調を維持しやすくなる。
        speaker = "ペルソナ" if item.role == "persona" else "ユーザー"
        history_lines.append(f"- {speaker}: {item.body}")

    history_block = "\n".join(history_lines) if history_lines else "- まだ会話履歴はありません"

    return (
        f"日付: {journal_date.isoformat()}\n"
        "\n"
        "この日の日記本文:\n"
        f"{journal_text}\n"
        "\n"
        "これまでの会話:\n"
        f"{history_block}\n"
        "\n"
        "今回のユーザーコメント:\n"
        f"{user_comment}"
    )


def _load_openrouter_config(max_output_tokens_default: int) -> _OpenRouterConfig:
    """環境変数から返信生成向け OpenRouter 設定を読み込む。"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.6-plus:free")
    # 新しい専用変数を優先し、未設定時のみ既存変数を後方互換として参照する。
    max_retries = _read_retry_count_env(default=2)
    max_output_tokens = read_int_env(
        "AI_JOURNAL_MAX_OUTPUT_TOKENS",
        default=max_output_tokens_default,
        minimum=1,
    )
    site_url = os.getenv("OPENROUTER_SITE_URL", "")
    site_name = os.getenv("OPENROUTER_SITE_NAME", "")

    return _OpenRouterConfig(
        api_key=api_key,
        model=model,
        max_retries=max_retries,
        max_output_tokens=max_output_tokens,
        site_url=site_url,
        site_name=site_name,
    )


def _create_llm(config: _OpenRouterConfig):
    """OpenRouter 接続設定済みの ChatOpenAI を返す。"""
    from langchain_openai import ChatOpenAI

    headers: dict[str, str] = {}
    if config.site_url:
        headers["HTTP-Referer"] = config.site_url
    if config.site_name:
        headers["X-Title"] = config.site_name

    return ChatOpenAI(
        model=config.model,
        temperature=0.7,
        api_key=config.api_key,
        base_url="https://openrouter.ai/api/v1",
        max_tokens=config.max_output_tokens,
        default_headers=headers if headers else None,
    )


def _read_retry_count_env(*, default: int) -> int:
    """返信用の再試行回数を読み込む（専用変数を優先）。"""
    persona_raw = os.getenv("AI_PERSONA_MAX_RETRIES")
    if persona_raw is not None and persona_raw.strip() != "":
        return read_int_env("AI_PERSONA_MAX_RETRIES", default=default, minimum=0)
    return read_int_env("AI_JOURNAL_MAX_RETRIES", default=default, minimum=0)


def _retry_delay_seconds(error: Exception, retry: int) -> float:
    """再試行までの待機秒数を計算する。"""
    retry_after = _retry_after_seconds(error)
    if retry_after is not None:
        return min(retry_after, 30.0)
    return float(min(2**retry, 8))


def _retry_after_seconds(error: Exception) -> float | None:
    """HTTP レスポンスの retry-after ヘッダーを秒で取得する。"""
    response = getattr(error, "response", None)
    if response is None:
        return None

    headers = getattr(response, "headers", None)
    if not headers:
        return None

    for key in ("retry-after", "Retry-After"):
        raw_value = headers.get(key)
        if raw_value is None:
            continue
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            continue
    return None


def _error_status_code(error: Exception) -> int | None:
    """例外オブジェクトから HTTP ステータスコードを抽出する。"""
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(error, "response", None)
    if response is None:
        return None

    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status
    return None


def _is_retryable_error(error: Exception) -> bool:
    """再試行対象の一時的エラーかどうかを判定する。"""
    status_code = _error_status_code(error)
    if status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
        return True

    message = str(error).lower()
    retryable_markers = (
        "rate-limit",
        "rate limited",
        "too many requests",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "service unavailable",
        "connection reset",
        "connection aborted",
        "429",
        "502",
        "503",
        "504",
    )
    return any(marker in message for marker in retryable_markers)
