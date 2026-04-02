import os
import time

from prompt_templates import load_prompt_section


# OpenRouterを使って日記本文を生成する。
def generate_with_openrouter(prompt: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.6-plus-preview:free")
    fallback_models_raw = os.getenv(
        "OPENROUTER_FALLBACK_MODELS",
        "openai/gpt-oss-120b:free",
    )
    max_retries = _read_int_env("AI_JOURNAL_MAX_RETRIES", default=1, minimum=0)
    # 1週間分(1日350〜450字)の出力に必要な量を考慮して既定値を高めにする。
    max_output_tokens = _read_int_env("AI_JOURNAL_MAX_OUTPUT_TOKENS", default=2600, minimum=1)
    site_url = os.getenv("OPENROUTER_SITE_URL", "")
    site_name = os.getenv("OPENROUTER_SITE_NAME", "")

    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("langchain / langchain-openai is not installed") from exc

    headers: dict[str, str] = {}
    if site_url:
        headers["HTTP-Referer"] = site_url
    if site_name:
        headers["X-Title"] = site_name

    system_text = load_prompt_section("System Prompt")

    # System/Humanの2メッセージ構成でLLMへ入力する。
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            ("human", "{user_prompt}"),
        ]
    )

    models = _build_model_candidates(model, fallback_models_raw)

    last_error: Exception | None = None
    for model_name in models:
        for retry in range(max_retries + 1):
            try:
                llm = ChatOpenAI(
                    model=model_name,
                    temperature=0.9,
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1",
                    max_tokens=max_output_tokens,
                    default_headers=headers if headers else None,
                )
                # PromptTemplate -> LLM -> 文字列パーサー のチェーンで実行。
                chain = prompt_template | llm | StrOutputParser()
                return chain.invoke({"user_prompt": prompt})
            except Exception as exc:
                last_error = exc
                if _is_model_unavailable_error(exc):
                    break
                if not _is_rate_limit_error(exc):
                    raise
                if retry < max_retries:
                    # 429時はサーバー指定の待機時間を優先し、なければ指数バックオフで再試行する。
                    time.sleep(_retry_delay_seconds(exc, retry))
                    continue
                break

    tried = ", ".join(models)
    raise RuntimeError(
        f"OpenRouterのレート制限により失敗しました。試行モデル: {tried}. "
        "無料枠は混雑すると失敗しやすいため、少し時間をおいて再実行するか、"
        "OPENROUTER_MODEL / OPENROUTER_FALLBACK_MODELS に別の無料モデルを設定してください。"
    ) from last_error


def _read_int_env(name: str, *, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def _build_model_candidates(primary: str, fallback_models_raw: str) -> list[str]:
    candidates: list[str] = []
    for raw_value in [primary, fallback_models_raw]:
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
