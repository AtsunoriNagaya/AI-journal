"""生成済み日記を閲覧する Web UI。"""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.viewer import (
    JournalEntry,
    JournalRepository,
    parse_iso_date,
    render_markdown_html,
    resolve_prev_next_dates,
)


_PROJECT_ROOT = Path(__file__).parent
_TEMPLATE_DIR = _PROJECT_ROOT / "webapp" / "templates"
_STATIC_DIR = _PROJECT_ROOT / "webapp" / "static"
_DEFAULT_JOURNALS_DIR = _PROJECT_ROOT / "journals"


def _resolve_journals_dir() -> Path:
    raw_path = os.getenv("AI_JOURNAL_JOURNALS_DIR", "").strip()
    if not raw_path:
        return _DEFAULT_JOURNALS_DIR
    return Path(raw_path).expanduser()


def _serialize_entry(entry: JournalEntry) -> dict[str, str]:
    return {
        "date": entry.journal_date.isoformat(),
        "excerpt": entry.excerpt,
        "char_count": str(len(entry.markdown_text)),
    }


def create_app(*, journals_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="AI Journal Viewer", version="0.1.0")
    app.state.repository = JournalRepository(journals_dir or _resolve_journals_dir())

    templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(
        request: Request,
        date_value: str | None = Query(default=None, alias="date"),
        q: str = Query(default=""),
    ):
        repository: JournalRepository = app.state.repository
        query = q.strip()
        entries = repository.list_entries(query=query)

        selected_date = _resolve_selected_date(entries, date_value)
        selected_entry = _pick_selected_entry(entries, selected_date)

        if selected_date is not None and selected_entry is None:
            raise HTTPException(status_code=404, detail="指定日の日記が見つかりません")

        previous_date, next_date = resolve_prev_next_dates(entries, selected_date)

        selected_html = ""
        if selected_entry is not None:
            selected_html = render_markdown_html(selected_entry.markdown_text)

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "entries": entries,
                "query": query,
                "query_suffix": f"&q={quote_plus(query)}" if query else "",
                "selected_entry": selected_entry,
                "selected_entry_html": selected_html,
                "previous_date": previous_date,
                "next_date": next_date,
                "journals_dir": str(repository.journals_dir),
            },
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

        try:
            target_date = parse_iso_date(journal_date)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        entry = repository.get_entry(target_date)
        if entry is None:
            raise HTTPException(status_code=404, detail="指定日の日記が見つかりません")

        all_entries = repository.list_entries()
        previous_date, next_date = resolve_prev_next_dates(all_entries, target_date)
        return {
            "date": entry.journal_date.isoformat(),
            "markdown": entry.markdown_text,
            "html": render_markdown_html(entry.markdown_text),
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


app = create_app()
