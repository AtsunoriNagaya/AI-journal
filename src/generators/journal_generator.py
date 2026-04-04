"""OpenRouter API を使用した日記生成モジュール。

責務:
    - OpenRouter API 設定の読み込みと検証
    - LangChain チェーンの構築と実行
    - 日別ループでの会話履歴管理（メモリベース）
    - stdout への進捗出力

このモジュールは API 通信と生成実行に特化し、設定解析や入力検証は行わない。
ペルソナ情報や設定は character_setting.py から受け取る。
"""

import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from src.input.character_setting import JournalSetting
from src.builders.prompt_builder import build_day_prompt
from src.templates.prompt_templates import load_prompt_section
from src.utils.env_utils import read_int_env


# prompts.md のパス（プロジェクトルートの config フォルダーを想定）
_PROMPTS_PATH = str(Path(__file__).parent.parent.parent / "config" / "prompts.md")


@dataclass(frozen=True)
class OpenRouterConfig:
    """OpenRouter API設定のコンテナ"""
    api_key: str
    model: str
    max_retries: int
    max_output_tokens: int
    site_url: str
    site_name: str


def _load_openrouter_config(max_output_tokens_default: int = 2600) -> OpenRouterConfig:
    """環境変数からOpenRouter設定を読み込む"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.6-plus:free")
    max_retries = read_int_env("AI_JOURNAL_MAX_RETRIES", default=1, minimum=0)
    max_output_tokens = read_int_env(
        "AI_JOURNAL_MAX_OUTPUT_TOKENS",
        default=max_output_tokens_default,
        minimum=1,
    )
    site_url = os.getenv("OPENROUTER_SITE_URL", "")
    site_name = os.getenv("OPENROUTER_SITE_NAME", "")

    return OpenRouterConfig(
        api_key=api_key,
        model=model,
        max_retries=max_retries,
        max_output_tokens=max_output_tokens,
        site_url=site_url,
        site_name=site_name,
    )


def generate_with_openrouter(
    prompt_or_setting: str | JournalSetting,
    *,
    output_dir: Path | None = None,
) -> str:
    """OpenRouter API を利用して日記本文を生成する。

    Args:
        prompt_or_setting: 直接のプロンプト文字列または JournalSetting オブジェクト。
            - 文字列の場合：一括生成モード（後方互換性用）
            - JournalSetting の場合：日別ループ + メモリモード（推奨）
        output_dir: 日別 Markdown 保存先ディレクトリ。None の場合は保存しない。

    Returns:
        生成された日記本文（複数日の場合は改行で区切られている）。

    Raises:
        RuntimeError: API キー未設定、モデル利用不可、またはレート制限で失敗時。
    """
    if isinstance(prompt_or_setting, JournalSetting):
        return _generate_with_history(prompt_or_setting, output_dir=output_dir)
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

    system_text = _load_prompt_context("System Prompt")
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            ("human", "{user_prompt}"),
        ]
    )

    last_error: Exception | None = None
    for retry in range(config.max_retries + 1):
        try:
            llm = _create_llm(config)
            # PromptTemplate -> LLM -> 文字列パーサー のチェーンで実行。
            chain = prompt_template | llm | StrOutputParser()
            return chain.invoke({"user_prompt": prompt})
        except Exception as exc:
            last_error = exc
            if not _is_rate_limit_error(exc):
                raise
            if retry < config.max_retries:
                # 429時はサーバー指定の待機時間を優先し、なければ指数バックオフで再試行する。
                time.sleep(_retry_delay_seconds(exc, retry))
                continue

    raise RuntimeError(
        "OpenRouterのレート制限により失敗しました。"
        "無料枠は混雑すると失敗しやすいため、少し時間をおいて再実行してください。"
    ) from last_error


def _generate_with_history(
    setting: JournalSetting,
    *,
    output_dir: Path | None = None,
) -> str:
    """日別ループで前日コンテキストを踏まえた日記を生成。

    LangChain の メッセージ履歴機能を使い、各日ごと に前日まで の会話を
    モデルに提供することで、矛盾や重複のない長編日記を生成する。

    Args:
        setting: 日記生成設定（期間、主人公、背景、イベント等）。
        output_dir: 日別 Markdown 保存先ディレクトリ。None の場合は保存しない。

    Returns:
        日別に生成された日記本文を改行で結合したもの。
        出力途中の各日分が リアルタイム で stdout に流される。
    """
    config = _load_openrouter_config(max_output_tokens_default=900)

    try:
        from langchain_core.chat_history import InMemoryChatMessageHistory
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain_core.runnables.history import RunnableWithMessageHistory
    except ImportError as exc:
        raise RuntimeError("langchain / langchain-openai is not installed") from exc

    # システムメッセージ + 会話履歴 + ユーザー入力 の3段構成で設定
    system_text = _load_prompt_context("System Prompt")
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{user_prompt}"),
        ]
    )

    llm = _create_llm(config)
    chain = prompt_template | llm | StrOutputParser()

    # セッション-ごとに会話履歴を保持する辞書
    history_store: dict[str, InMemoryChatMessageHistory] = {}

    def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
        """セッション ID に紐づく履歴を取得、未作成なら新規作成。"""
        if session_id not in history_store:
            history_store[session_id] = InMemoryChatMessageHistory()
        return history_store[session_id]

    # メモリを統合したチェーン構築
    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="user_prompt",
        history_messages_key="history",
    )

    # 日別ループ：各日ごとにプロンプト → 実行 → 出力
    diary_parts: list[str] = []
    for day_number in range(1, setting.days + 1):
        previous_summary = _build_previous_summary(diary_parts)
        avoid_repetition_hint = _build_avoidance_hint(diary_parts, setting)
        daily_prompt = build_day_prompt(
            setting,
            day_number,
            previous_summary=previous_summary,
            avoid_repetition_hint=avoid_repetition_hint,
        )
        day_diary = _invoke_daily_prompt(
            chain_with_history,
            daily_prompt,
            max_retries=config.max_retries,
        ).strip()
        diary_parts.append(day_diary)
        print(day_diary, flush=True)
        try:
            _save_day_diary_markdown(
                output_dir=output_dir,
                start_date=setting.start_date,
                day_number=day_number,
                diary_text=day_diary,
            )
        except OSError as error:
            print(
                f"[WARN] 日記ファイルの保存に失敗しました ({day_number}日目): {error}",
                file=sys.stderr,
                flush=True,
            )
        if day_number < setting.days:
            print(flush=True)

    return "\n\n".join(diary_parts)


def _create_llm(config: OpenRouterConfig):
    """OpenRouter 用の LangChain ChatOpenAI インスタンスを生成。

    Args:
        config: OpenRouter 設定。

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
        model=config.model,
        temperature=0.9,
        api_key=config.api_key,
        base_url="https://openrouter.ai/api/v1",
        max_tokens=config.max_output_tokens,
        default_headers=headers if headers else None,
    )


def _load_prompt_context(section_name: str) -> str:
    """指定セクションと共通ガイドラインを連結して返す。"""
    # どのモードでも Common Guidelines を同時適用する方針。
    base_text = load_prompt_section(section_name, _PROMPTS_PATH)
    common_text = load_prompt_section("Common Guidelines", _PROMPTS_PATH)
    return f"{base_text}\n\n{common_text}"


def _invoke_daily_prompt(chain_with_history, prompt: str, *, max_retries: int) -> str:
    """1日分のプロンプト実行を行い、必要なら再試行する。"""
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
                # レート制限時のみ待機してリトライする。
                time.sleep(_retry_delay_seconds(exc, retry))
                continue
            raise

    raise RuntimeError("日記生成に失敗しました") from last_error


def _build_previous_summary(diary_parts: list[str], *, max_items: int = 2) -> str:
    """直近の日記を短い要約箇条書きへ変換する。"""
    if not diary_parts:
        return "- まだ前日までの記録はありません（1日目）。"

    start_index = max(0, len(diary_parts) - max_items)
    lines: list[str] = []
    for index in range(start_index, len(diary_parts)):
        day_number = index + 1
        body_text = _extract_body_text(diary_parts[index])
        snippet = body_text[:90].rstrip()
        if len(body_text) > 90:
            snippet += "..."
        lines.append(f"- {day_number}日目: {snippet}")
    return "\n".join(lines)


def _extract_body_text(diary_text: str) -> str:
    """見出しを除いた本文だけを抽出して 1 行へ整形する。"""
    lines = [line.strip() for line in diary_text.splitlines() if line.strip()]
    if not lines:
        return "記録なし"

    first_line = lines[0]
    if re.fullmatch(r"(##\s*)?(\d{2}/\d{2}|\d{4}-\d{2}-\d{2})", first_line):
        lines = lines[1:]

    body = " ".join(lines).strip()
    return body if body else "記録なし"


def _build_avoidance_hint(
    diary_parts: list[str],
    setting: JournalSetting,
    *,
    lookback_days: int = 3,
    max_terms: int = 6,
) -> str:
    """直近数日の反復語を検出し、重複回避ヒントを作る。"""
    if len(diary_parts) < 2:
        return "なし"

    watched_terms = _collect_watch_terms(setting)

    recent_text = " ".join(
        _extract_body_text(part)
        for part in diary_parts[-lookback_days:]
    )

    matched = [term for term in watched_terms if term in recent_text]
    if not matched:
        return "なし"

    # 順序を保ったまま重複を取り除く。
    unique_terms = list(dict.fromkeys(matched))[:max_terms]
    return "次の語やモチーフの連続使用を避ける: " + "、".join(unique_terms)


def _collect_watch_terms(setting: JournalSetting) -> list[str]:
    """重複監視の対象語を設定値から収集する。"""
    source_text = " ".join(
        [
            setting.living_area,
            setting.hobbies,
            setting.concerns,
            setting.likely_events,
            setting.avoid_patterns,
            setting.growth_direction,
            " ".join(incident.content for incident in setting.incidents),
        ]
    )

    base_terms = _split_candidate_terms(source_text)
    style_terms = [
        "少しずつ",
        "静か",
        "手応え",
        "呼吸",
        "肩の力",
        "整える",
    ]
    merged = base_terms + style_terms
    return list(dict.fromkeys(merged))


def _split_candidate_terms(text: str) -> list[str]:
    """監視候補の語を簡易分割し、ノイズ語を除外する。"""
    parts = re.split(r"[、。,，\s/・（）()「」『』【】]+", text)
    stop_words = {
        "こと",
        "もの",
        "ため",
        "よう",
        "など",
        "ある",
        "いる",
        "する",
        "なる",
        "できる",
        "状態",
        "方向",
        "感じ",
        "自分",
        "今日",
        "明日",
    }

    terms: list[str] = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if token in stop_words:
            continue
        if len(token) < 2 or len(token) > 18:
            continue
        # 長すぎる句や 1 文字語は一致判定のノイズになりやすいので除外する。
        terms.append(token)
    return terms


def _save_day_diary_markdown(
    *,
    output_dir: Path | None,
    start_date: date,
    day_number: int,
    diary_text: str,
) -> Path | None:
    """1日分の日記を YYYY-MM-DD.md として保存する。"""
    if output_dir is None:
        return None
    if day_number < 1:
        raise ValueError("day_number must be 1 or greater")

    target_date = start_date + timedelta(days=day_number - 1)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{target_date.isoformat()}.md"
    output_path.write_text(diary_text, encoding="utf-8")
    return output_path


def _retry_delay_seconds(error: Exception, retry: int) -> float:
    """次回リトライまでの待機秒数を計算する。"""
    retry_after = _retry_after_seconds(error)
    if retry_after is not None:
        return min(retry_after, 30.0)
    return float(min(2**retry, 8))


def _retry_after_seconds(error: Exception) -> float | None:
    """レスポンスヘッダーから retry-after 秒数を取り出す。"""
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
    """エラーがレート制限由来かどうかを判定する。"""
    status_code = getattr(error, "status_code", None)
    if status_code == 429:
        return True
    message = str(error).lower()
    return "429" in message and ("rate-limit" in message or "rate limited" in message)
