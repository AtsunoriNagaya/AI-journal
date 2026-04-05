"""生成済み日記を閲覧する Web UI。"""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import sys
from typing import Protocol
from urllib.parse import quote_plus, urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.viewer import (
    CommentRepository,
    JournalEntry,
    JournalComment,
    JournalRepository,
    PersonaReplyService,
    parse_iso_date,
    render_markdown_html,
    resolve_prev_next_dates,
)
from src.utils.text_utils import compact_text


_PROJECT_ROOT = Path(__file__).parent
_TEMPLATE_DIR = _PROJECT_ROOT / "webapp" / "templates"
_STATIC_DIR = _PROJECT_ROOT / "webapp" / "static"
_DEFAULT_JOURNALS_DIR = _PROJECT_ROOT / "journals"
_DEFAULT_PERSONA_PATH = _PROJECT_ROOT / "config" / "persona.md"


class PersonaReplyGenerator(Protocol):
    """ペルソナ返信サービスの最小インターフェース。"""

    persona_name: str

    def generate_reply(
        self,
        *,
        journal_date: date,
        journal_text: str,
        user_comment: str,
        recent_comments: list[JournalComment],
    ) -> str:
        ...


def _resolve_journals_dir() -> Path:
    """日記ディレクトリを環境変数優先で決定する。"""
    raw_path = os.getenv("AI_JOURNAL_JOURNALS_DIR", "").strip()
    if not raw_path:
        return _DEFAULT_JOURNALS_DIR
    return Path(raw_path).expanduser()


def _resolve_persona_path() -> Path:
    """ペルソナ設定ファイルのパスを環境変数優先で決定する。"""
    raw_path = os.getenv("AI_JOURNAL_PERSONA_PATH", "").strip()
    if not raw_path:
        return _DEFAULT_PERSONA_PATH
    return Path(raw_path).expanduser()


def _serialize_entry(entry: JournalEntry) -> dict[str, object]:
    """JournalEntry を API 応答用の辞書に変換する。"""
    return {
        "date": entry.journal_date.isoformat(),
        "excerpt": entry.excerpt,
        "char_count": len(entry.markdown_text),
    }


def _serialize_comment(comment: JournalComment) -> dict[str, str]:
    """JournalComment を API 応答用の辞書に変換する。"""
    return {
        "id": comment.comment_id,
        "author": comment.author,
        "role": comment.role,
        "body": comment.body,
        "created_at": comment.created_at_iso,
    }


def create_app(
    *,
    journals_dir: Path | None = None,
    persona_reply_service: PersonaReplyGenerator | None = None,
) -> FastAPI:
    # uvicorn 経由で起動した場合でも .env を自動で読む。
    load_dotenv(_PROJECT_ROOT / ".env")

    app = FastAPI(title="AI Journal Viewer", version="0.1.0")
    resolved_journals_dir = journals_dir or _resolve_journals_dir()

    app.state.repository = JournalRepository(resolved_journals_dir)
    app.state.comment_repository = CommentRepository()
    app.state.persona_reply_service = persona_reply_service or PersonaReplyService(_resolve_persona_path())

    templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(
        request: Request,
        date_value: str | None = Query(default=None, alias="date"),
        q: str = Query(default=""),
        comment_error: str = Query(default=""),
        comment_saved: str = Query(default=""),
    ):
        # app.state に依存オブジェクトを置くことで、テスト時に差し替えやすくしている。
        repository: JournalRepository = app.state.repository
        comment_repository: CommentRepository = app.state.comment_repository
        reply_service: PersonaReplyGenerator = app.state.persona_reply_service
        query = q.strip()

        # 左側一覧に表示する日記一覧（検索語があれば本文検索を適用）。
        entries = repository.list_entries(query=query)
        persona_view = _build_persona_view(reply_service)

        # date 指定が無ければ先頭（最新）を開く。
        selected_date = _resolve_selected_date(entries, date_value)
        selected_entry = _pick_selected_entry(entries, selected_date)

        if selected_date is not None and selected_entry is None:
            raise HTTPException(status_code=404, detail="指定日の日記が見つかりません")

        previous_date, next_date = resolve_prev_next_dates(entries, selected_date)

        # 選択日がある場合のみ本文HTMLとコメント一覧を準備する。
        selected_html = ""
        comments: list[JournalComment] = []
        if selected_entry is not None:
            selected_html = render_markdown_html(selected_entry.markdown_text)
            comments = comment_repository.list_comments(selected_entry.journal_date)

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "entries": entries,
                "query": query,
                "query_suffix": f"&q={quote_plus(query)}" if query else "",
                "selected_entry": selected_entry,
                "selected_entry_html": selected_html,
                "previous_date": previous_date,
                "next_date": next_date,
                "journals_dir": str(repository.journals_dir),
                "comments": comments,
                "comment_error": comment_error.strip(),
                "comment_saved": comment_saved == "1",
                "persona_name": persona_view["name"],
                "persona_background": persona_view["background"],
                "persona_tone_keywords": persona_view["tone_keywords"],
            },
        )

    @app.post("/comments/{journal_date}")
    def add_comment(
        journal_date: str,
        q: str = Query(default=""),
        # コメントフォームの hidden input(name="q") から検索語を引き継ぐ。
        q_form: str = Form(default="", alias="q"),
        author: str = Form(default=""),
        body: str = Form(default=""),
    ):
        repository: JournalRepository = app.state.repository
        comment_repository: CommentRepository = app.state.comment_repository
        reply_service: PersonaReplyGenerator = app.state.persona_reply_service

        # URL パラメーターの日付は文字列で来るため、最初に厳密な日付へ変換する。
        try:
            target_date = parse_iso_date(journal_date)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        # 日記が存在しない日付にはコメントできないようにする。
        entry = repository.get_entry(target_date)
        if entry is None:
            raise HTTPException(status_code=404, detail="指定日の日記が見つかりません")

        # URL で明示された検索語を優先し、無ければフォーム hidden 値を使う。
        effective_query = _resolve_effective_query(
            query=q,
            query_from_form=q_form,
        )

        # 入力値バリデーション（空コメントなど）は repository 側に委譲する。
        try:
            saved_user_comment = comment_repository.add_comment(
                target_date=target_date,
                author=author,
                role="user",
                body=body,
            )
        except ValueError as error:
            # 入力エラー時は同じページへ戻し、エラーメッセージだけを表示する。
            return _redirect_to_home(
                target_date=target_date,
                query=effective_query,
                comment_error=str(error),
            )

        # ユーザーコメント保存後に、ペルソナ返信の生成・保存を試みる。
        reply_warning = _save_persona_reply_or_warning(
            reply_service=reply_service,
            comment_repository=comment_repository,
            target_date=target_date,
            journal_text=entry.markdown_text,
            saved_user_comment=saved_user_comment,
        )

        # 投稿完了後は PRG パターンで GET に戻す（リロード時の二重投稿防止）。
        return _redirect_to_home(
            target_date=target_date,
            query=effective_query,
            comment_saved=True,
            comment_error=reply_warning,
        )

    @app.get("/api/journals")
    def list_journals(q: str = Query(default="")) -> dict[str, object]:
        repository: JournalRepository = app.state.repository
        entries = repository.list_entries(query=q.strip())
        return {
            "count": len(entries),
            "items": [_serialize_entry(entry) for entry in entries],
        }

    @app.get("/api/journals/{journal_date}")
    def get_journal(journal_date: str) -> dict[str, object]:
        repository: JournalRepository = app.state.repository
        comment_repository: CommentRepository = app.state.comment_repository

        try:
            target_date = parse_iso_date(journal_date)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        entry = repository.get_entry(target_date)
        if entry is None:
            raise HTTPException(status_code=404, detail="指定日の日記が見つかりません")

        comments = comment_repository.list_comments(target_date)
        all_entries = repository.list_entries()
        previous_date, next_date = resolve_prev_next_dates(all_entries, target_date)
        return {
            "date": entry.journal_date.isoformat(),
            "markdown": entry.markdown_text,
            "html": render_markdown_html(entry.markdown_text),
            "comment_count": len(comments),
            "comments": [_serialize_comment(comment) for comment in comments],
            "previous_date": previous_date.isoformat() if previous_date else None,
            "next_date": next_date.isoformat() if next_date else None,
        }

    return app


def _resolve_effective_query(*, query: str, query_from_form: str) -> str:
    """URL query を優先し、空ならフォーム値を採用する。"""
    # URL の query はユーザーが直接変更できるため、hidden より優先する。
    normalized_query = query.strip()
    if normalized_query:
        return normalized_query
    return query_from_form.strip()


def _redirect_to_home(
    *,
    target_date: date,
    query: str,
    comment_error: str = "",
    comment_saved: bool = False,
) -> RedirectResponse:
    """ホーム画面への 303 リダイレクトを生成する。"""
    destination = _build_home_url(
        target_date=target_date,
        query=query,
        comment_error=comment_error,
        comment_saved=comment_saved,
    )
    return RedirectResponse(url=destination, status_code=303)


def _save_persona_reply_or_warning(
    *,
    reply_service: PersonaReplyGenerator,
    comment_repository: CommentRepository,
    target_date: date,
    journal_text: str,
    saved_user_comment: JournalComment,
) -> str:
    """ペルソナ返信を保存し、失敗時は警告文言を返す。"""
    # 直前に保存したユーザーコメントは「今回の入力」として別枠で渡すため、
    # 履歴重複を避ける目的で除外している。
    recent_comments_for_reply = [
        comment
        for comment in comment_repository.list_comments(target_date)
        if comment.comment_id != saved_user_comment.comment_id
    ]

    try:
        persona_reply = reply_service.generate_reply(
            journal_date=target_date,
            journal_text=journal_text,
            user_comment=saved_user_comment.body,
            recent_comments=recent_comments_for_reply,
        )
        comment_repository.add_comment(
            target_date=target_date,
            author=_safe_persona_name(reply_service),
            role="persona",
            body=persona_reply,
        )
        return ""
    except Exception as error:
        # 返信生成に失敗しても、ユーザーコメント自体は保存済みなので処理継続する。
        error_detail = _format_error_chain(error)
        print(
            f"[WARN] ペルソナ返信の生成に失敗しました: {error_detail}",
            file=sys.stderr,
            flush=True,
        )
        return "コメントは保存しましたが、ペルソナ返信の生成に失敗しました。"


def _resolve_selected_date(entries: list[JournalEntry], raw_date: str | None) -> date | None:
    """表示対象の日付を解決する。"""
    if raw_date is None:
        if not entries:
            return None
        # date 指定が無ければ、最新日記（降順の先頭）を表示する。
        return entries[0].journal_date

    try:
        return parse_iso_date(raw_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _pick_selected_entry(
    entries: list[JournalEntry],
    selected_date: date | None,
) -> JournalEntry | None:
    """一覧から対象日の日記を 1 件取り出す。"""
    if selected_date is None:
        return None

    for item in entries:
        if item.journal_date == selected_date:
            return item
    return None


def _build_home_url(
    *,
    target_date: date,
    query: str,
    comment_error: str = "",
    comment_saved: bool = False,
) -> str:
    """ホーム画面URLをクエリ付きで組み立てる。"""
    params: dict[str, str] = {"date": target_date.isoformat()}
    normalized_query = query.strip()
    if normalized_query:
        params["q"] = normalized_query
    if comment_error:
        params["comment_error"] = comment_error
    if comment_saved:
        params["comment_saved"] = "1"
    return f"/?{urlencode(params)}"


def _build_persona_view(reply_service: PersonaReplyGenerator) -> dict[str, str]:
    """UI表示用のペルソナ情報を安全に整形して返す。"""
    name = _safe_persona_name(reply_service)

    background = _safe_persona_field(
        reply_service,
        field_name="persona_background",
        max_length=110,
    )
    tone_keywords = _safe_persona_field(
        reply_service,
        field_name="persona_tone_keywords",
        max_length=56,
    )
    return {
        "name": name,
        "background": background,
        "tone_keywords": tone_keywords,
    }


def _safe_persona_name(reply_service: PersonaReplyGenerator) -> str:
    """表示用ペルソナ名を取得する。失敗時は既定名を返す。"""
    name = _safe_persona_field(
        reply_service,
        field_name="persona_name",
        max_length=38,
    )
    return name or "ペルソナ"


def _safe_persona_field(
    reply_service: PersonaReplyGenerator,
    *,
    field_name: str,
    max_length: int,
) -> str:
    """返信サービスから属性を安全に取得し、表示向けに短く整形する。"""
    try:
        value = getattr(reply_service, field_name, "")
    except Exception as error:
        print(
            f"[WARN] ペルソナ情報の取得に失敗しました({field_name}): {_format_error_chain(error)}",
            file=sys.stderr,
            flush=True,
        )
        return ""

    return _compact_text(value, max_length=max_length)


def _compact_text(raw_value: object, *, max_length: int) -> str:
    """表示用テキストの空白を正規化し、最大文字数までに切り詰める。"""
    if not isinstance(raw_value, str):
        return ""

    normalized = compact_text(raw_value)
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "…"


def _format_error_chain(error: Exception) -> str:
    """例外チェーンを 1 行文字列に連結する。"""
    parts: list[str] = []
    current: BaseException | None = error
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        message = str(current).strip() or "(no message)"
        parts.append(f"{type(current).__name__}: {message}")

        # 明示的な cause があればそれを優先し、無ければ context をたどる。
        if current.__cause__ is not None:
            current = current.__cause__
        elif getattr(current, "__suppress_context__", False):
            current = None
        else:
            current = current.__context__

    return " <- ".join(parts)


app = create_app()
