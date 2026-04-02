"""OpenRouter API を使用した日記生成モジュール。

責務:
  - OpenRouter API 設定の読み込みと検証
  - LangChain チェーンの構築と実行
  - モデルフォールバックとレート制限時の再試行ロジック
  - 日別ループでの会話履歴管理（メモリベース）
  - stdout への進捗出力

このモジュールは API 通信と生成実行に特化し、設定解析や入力検証は行わない。
ペルソナ情報や設定は character_setting.py から受け取る。
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path

from src.input.character_setting import JournalSetting
from src.builders.prompt_builder import build_day_prompt
from src.templates.prompt_templates import load_prompt_section


# prompts.md のパス（プロジェクトルートの config フォルダーを想定）
_PROMPTS_PATH = str(Path(__file__).parent.parent.parent / "config" / "prompts.md")


@dataclass(frozen=True)
class OpenRouterConfig:
    """OpenRouter API設定のコンテナ"""
    api_key: str
    model: str
    fallback_models: list[str]
    max_retries: int
    max_output_tokens: int
    site_url: str
    site_name: str


def _load_openrouter_config(max_output_tokens_default: int = 2600) -> OpenRouterConfig:
    """環境変数からOpenRouter設定を読み込む"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.6-plus-preview:free")
    fallback_models_raw = os.getenv(
        "OPENROUTER_FALLBACK_MODELS",
        "openai/gpt-oss-120b:free",
    )
    max_retries = _read_int_env("AI_JOURNAL_MAX_RETRIES", default=1, minimum=0)
    max_output_tokens = _read_int_env("AI_JOURNAL_MAX_OUTPUT_TOKENS", default=max_output_tokens_default, minimum=1)
    site_url = os.getenv("OPENROUTER_SITE_URL", "")
    site_name = os.getenv("OPENROUTER_SITE_NAME", "")
    fallback_models = _build_model_candidates(model, fallback_models_raw)

    return OpenRouterConfig(
        api_key=api_key,
        model=model,
        fallback_models=fallback_models,
        max_retries=max_retries,
        max_output_tokens=max_output_tokens,
        site_url=site_url,
        site_name=site_name,
    )


def generate_with_openrouter(prompt_or_setting: str | JournalSetting) -> str:
    """OpenRouter API を利用して日記本文を生成する。

    Args:
        prompt_or_setting: 直接のプロンプト文字列または JournalSetting オブジェクト。
            - 文字列の場合：一括生成モード（後方互換性用）
            - JournalSetting の場合：日別ループ + メモリモード（推奨）

    Returns:
        生成された日記本文（複数日の場合は改行で区切られている）。

    Raises:
        RuntimeError: API キー未設定、モデル利用不可、またはレート制限で失敗時。
    """
    if isinstance(prompt_or_setting, JournalSetting):
        return _generate_with_history(prompt_or_setting)
    return _generate_single_prompt(prompt_or_setting)


def _generate_single_prompt(prompt: str) -> str:
    """1つのプロンプトを一括で生成（後方互換モード）。

    Args:
        prompt: 生成対象のプロンプト文字列。

    Returns:
        LLM の出力結果。
    """
    config = _load_openrouter_config(max_output_tokens_default=2600)

    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:
        raise RuntimeError("langchain / langchain-openai is not installed") from exc

    system_text = load_prompt_section("System Prompt", _PROMPTS_PATH)
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            ("human", "{user_prompt}"),
        ]
    )

    last_error: Exception | None = None
    for model_name in config.fallback_models:
        for retry in range(config.max_retries + 1):
            try:
                llm = _create_llm(config, model_name)
                # PromptTemplate -> LLM -> 文字列パーサー のチェーンで実行。
                chain = prompt_template | llm | StrOutputParser()
                return chain.invoke({"user_prompt": prompt})
            except Exception as exc:
                last_error = exc
                if _is_model_unavailable_error(exc):
                    break
                if not _is_rate_limit_error(exc):
                    raise
                if retry < config.max_retries:
                    # 429時はサーバー指定の待機時間を優先し、なければ指数バックオフで再試行する。
                    time.sleep(_retry_delay_seconds(exc, retry))
                    continue
                break

    tried = ", ".join(config.fallback_models)
    raise RuntimeError(
        f"OpenRouterのレート制限により失敗しました。試行モデル: {tried}. "
        "無料枠は混雑すると失敗しやすいため、少し時間をおいて再実行するか、"
        "OPENROUTER_MODEL / OPENROUTER_FALLBACK_MODELS に別の無料モデルを設定してください。"
    ) from last_error


def _generate_with_history(setting: JournalSetting) -> str:
    """日別ループで前日コンテキストを踏まえた日記を生成。

    LangChain の メッセージ履歴機能を使い、各日ごと に前日まで の会話を
    モデルに提供することで、矛盾や重複のない長編日記を生成する。

    Args:
        setting: 日記生成設定（期間、主人公、背景、イベント等）。

    Returns:
        日別に生成された日記本文を改行で結合したもの。
        出力途中の各日分が リアルタイム で stdout に流される。
    """
    config = _load_openrouter_config(max_output_tokens_default=1500)

    try:
        from langchain_core.chat_history import InMemoryChatMessageHistory
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain_core.runnables.history import RunnableWithMessageHistory
    except ImportError as exc:
        raise RuntimeError("langchain / langchain-openai is not installed") from exc

    # システムメッセージ + 会話履歴 + ユーザー入力 の3段構成で設定
    system_text = load_prompt_section("System Prompt", _PROMPTS_PATH)
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{user_prompt}"),
        ]
    )

    last_error: Exception | None = None

    # モデル候補を順に試す（フォールバック）
    for model_name in config.fallback_models:
        try:
            llm = _create_llm(config, model_name)
            chain = prompt_template | llm | StrOutputParser()
            
            # セッション-ごとに会話履歴を保持する辞書
            # （同一セッション内で複数日の履歴が蓄積される）
            history_store: dict[str, InMemoryChatMessageHistory] = {}

            def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
                """セッション ID に紐づく履歴を取得、未作成なら新規作成。"""
                if session_id not in history_store:
                    history_store[session_id] = InMemoryChatMessageHistory()
                return history_store[session_id]

            # メモリを統合したチェーン構築
            # get_session_history が各呼び出しで前日まで の会話を供給する
            chain_with_history = RunnableWithMessageHistory(
                chain,
                get_session_history,
                input_messages_key="user_prompt",
                history_messages_key="history",
            )

            # 日別ループ：各日ごとにプロンプト → 実行 → 出力
            diary_parts: list[str] = []
            for day_number in range(1, setting.days + 1):
                daily_prompt = build_day_prompt(setting, day_number)
                day_diary = _invoke_daily_prompt(
                    chain_with_history,
                    daily_prompt,
                    max_retries=config.max_retries,
                ).strip()
                diary_parts.append(day_diary)
                print(day_diary, flush=True)
                if day_number < setting.days:
                    print(flush=True)

            return "\n\n".join(diary_parts)

        except Exception as exc:
            last_error = exc
            if _is_model_unavailable_error(exc) or _is_rate_limit_error(exc):
                continue
            raise

    tried = ", ".join(config.fallback_models)
    raise RuntimeError(
        f"OpenRouterのレート制限またはモデル未提供により失敗しました。試行モデル: {tried}. "
        "無料枠は混雑すると失敗しやすいため、少し時間をおいて再実行するか、"
        "OPENROUTER_MODEL / OPENROUTER_FALLBACK_MODELS に別の無料モデルを設定してください。"
    ) from last_error


def _create_llm(config: OpenRouterConfig, model_name: str):
    """OpenRouter 用の LangChain ChatOpenAI インスタンスを生成。

    Args:
        config: OpenRouter 設定。
        model_name: 利用するモデル名（例：qwen/qwen3.6-plus-preview:free）。

    Returns:
        構成済みの ChatOpenAI インスタンス。
    """
    from langchain_openai import ChatOpenAI

    # OpenRouter の識別用ヘッダーを構築（site_url / site_name は任意）
    headers: dict[str, str] = {}
    if config.site_url:
        headers["HTTP-Referer"] = config.site_url
    if config.site_name:
        headers["X-Title"] = config.site_name

    return ChatOpenAI(
        model=model_name,
        temperature=0.9,
        api_key=config.api_key,
        base_url="https://openrouter.ai/api/v1",
        max_tokens=config.max_output_tokens,
        default_headers=headers if headers else None,
    )


def _invoke_daily_prompt(chain_with_history, prompt: str, *, max_retries: int) -> str:
    last_error: Exception | None = None
    for retry in range(max_retries + 1):
        try:
            return chain_with_history.invoke(
                {"user_prompt": prompt},
                config={"configurable": {"session_id": "journal"}},
            )
        except Exception as exc:
            last_error = exc
            if not _is_rate_limit_error(exc):
                raise
            if retry < max_retries:
                time.sleep(_retry_delay_seconds(exc, retry))
                continue
            raise

    raise RuntimeError("日記生成に失敗しました") from last_error


def _read_int_env(name: str, *, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def _build_model_candidates(primary: str, fallback_models_raw: str | None = None) -> list[str]:
    """プライマリとフォールバックモデルをマージ"""
    candidates: list[str] = []
    for raw_value in [primary, fallback_models_raw or ""]:
        if not raw_value:
            continue
        for model_name in raw_value.split(","):
            stripped = model_name.strip()
            if stripped and stripped not in candidates:
                candidates.append(stripped)
    return candidates


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


def _is_model_unavailable_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code == 404:
        return True
    message = str(error).lower()
    return "no endpoints found" in message or ("404" in message and "model" in message)
