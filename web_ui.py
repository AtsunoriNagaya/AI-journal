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


_PROJECT_ROOT = Path(__file__).parent
_TEMPLATE_DIR = _PROJECT_ROOT / "webapp" / "templates"
_STATIC_DIR = _PROJECT_ROOT / "webapp" / "static"
_DEFAULT_JOURNALS_DIR = _PROJECT_ROOT / "journals"
_DEFAULT_PERSONA_PATH = _PROJECT_ROOT / "config" / "persona.md"


class PersonaReplyGenerator(Protocol):
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
    raw_path = os.getenv("AI_JOURNAL_JOURNALS_DIR", "").strip()
    if not raw_path:
        return _DEFAULT_JOURNALS_DIR
    return Path(raw_path).expanduser()


def _resolve_persona_path() -> Path:
    raw_path = os.getenv("AI_JOURNAL_PERSONA_PATH", "").strip()
    if not raw_path:
        return _DEFAULT_PERSONA_PATH
    return Path(raw_path).expanduser()


def _serialize_entry(entry: JournalEntry) -> dict[str, object]:
    return {
        "date": entry.journal_date.isoformat(),
        "excerpt": entry.excerpt,
        "char_count": len(entry.markdown_text),
    }


def _serialize_comment(comment: JournalComment) -> dict[str, str]:
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
        repository: JournalRepository = app.state.repository
        comment_repository: CommentRepository = app.state.comment_repository
        reply_service: PersonaReplyGenerator = app.state.persona_reply_service
        query = q.strip()
        entries = repository.list_entries(query=query)
        persona_view = _build_persona_view(reply_service)

        selected_date = _resolve_selected_date(entries, date_value)
        selected_entry = _pick_selected_entry(entries, selected_date)

        if selected_date is not None and selected_entry is None:
            raise HTTPException(status_code=404, detail="指定日の日記が見つかりません")

        previous_date, next_date = resolve_prev_next_dates(entries, selected_date)

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
        q_form: str = Form(default=""),
        author: str = Form(default=""),
        body: str = Form(default=""),
    ):
        repository: JournalRepository = app.state.repository
        comment_repository: CommentRepository = app.state.comment_repository
        reply_service: PersonaReplyGenerator = app.state.persona_reply_service

        try:
            target_date = parse_iso_date(journal_date)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        entry = repository.get_entry(target_date)
        if entry is None:
            raise HTTPException(status_code=404, detail="指定日の日記が見つかりません")

        effective_query = q.strip() if q.strip() else q_form.strip()

        try:
            comment_repository.add_comment(
                target_date=target_date,
                author=author,
                role="user",
                body=body,
            )
        except ValueError as error:
            destination = _build_home_url(
                target_date=target_date,
                query=effective_query,
                comment_error=str(error),
            )
            return RedirectResponse(url=destination, status_code=303)

        reply_warning = ""
        try:
            recent_comments = comment_repository.list_comments(target_date)
            persona_reply = reply_service.generate_reply(
                journal_date=target_date,
                journal_text=entry.markdown_text,
                user_comment=body,
                recent_comments=recent_comments,
            )
            comment_repository.add_comment(
                target_date=target_date,
                author=reply_service.persona_name,
                role="persona",
                body=persona_reply,
            )
        except Exception as error:
            print(
                f"[WARN] ペルソナ返信の生成に失敗しました: {error}",
                file=sys.stderr,
                flush=True,
            )
            reply_warning = "コメントは保存しましたが、ペルソナ返信の生成に失敗しました。"

        destination = _build_home_url(
            target_date=target_date,
            query=effective_query,
            comment_saved=True,
            comment_error=reply_warning,
        )
        return RedirectResponse(url=destination, status_code=303)

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


def _resolve_selected_date(entries: list[JournalEntry], raw_date: str | None) -> date | None:
    if raw_date is None:
        if not entries:
            return None
        return entries[0].journal_date

    try:
        return parse_iso_date(raw_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _pick_selected_entry(
    entries: list[JournalEntry],
    selected_date: date | None,
) -> JournalEntry | None:
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
    name = _compact_text(getattr(reply_service, "persona_name", "ペルソナ"), max_length=38)
    if not name:
        name = "ペルソナ"

    background = _compact_text(getattr(reply_service, "persona_background", ""), max_length=110)
    tone_keywords = _compact_text(getattr(reply_service, "persona_tone_keywords", ""), max_length=56)
    return {
        "name": name,
        "background": background,
        "tone_keywords": tone_keywords,
    }


def _compact_text(raw_value: object, *, max_length: int) -> str:
    if not isinstance(raw_value, str):
        return ""

    normalized = " ".join(part.strip() for part in raw_value.replace("\r\n", "\n").splitlines() if part.strip())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "…"


app = create_app()
