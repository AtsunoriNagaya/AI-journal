"""コメントに対するペルソナ返信の生成サービス。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
import time

from src.input.character_setting import JournalSetting, load_setting_from_markdown
from src.viewer.comment_repository import JournalComment


@dataclass(frozen=True)
class _OpenRouterConfig:
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
        config = _load_openrouter_config(max_output_tokens_default=320)

        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate
        except ImportError as exc:
            raise RuntimeError("langchain / langchain-openai is not installed") from exc

        setting = self._setting
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
                if not _is_rate_limit_error(exc):
                    raise RuntimeError("ペルソナ返信の生成に失敗しました") from exc
                if retry < config.max_retries:
                    time.sleep(_retry_delay_seconds(exc, retry))
                    continue

        raise RuntimeError("ペルソナ返信の生成に失敗しました") from last_error

    @property
    def _setting(self) -> JournalSetting:
        if self._setting_cache is None:
            self._setting_cache = load_setting_from_markdown(str(self._persona_path))
        return self._setting_cache


def _build_system_prompt(setting: JournalSetting) -> str:
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
    history_lines: list[str] = []
    for item in recent_comments[-6:]:
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
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.6-plus-preview:free")
    max_retries = _read_int_env("AI_JOURNAL_MAX_RETRIES", default=1, minimum=0)
    max_output_tokens = _read_int_env(
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


def _read_int_env(name: str, *, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def _retry_delay_seconds(error: Exception, retry: int) -> float:
    retry_after = _retry_after_seconds(error)
    if retry_after is not None:
        return min(retry_after, 30.0)
    return float(min(2**retry, 8))


def _retry_after_seconds(error: Exception) -> float | None:
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


def _is_rate_limit_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code == 429:
        return True
    message = str(error).lower()
    return "429" in message and ("rate-limit" in message or "rate limited" in message)
