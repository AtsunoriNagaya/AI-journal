"""journals 配下の Markdown 日記を読み込むユーティリティ。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re


_FILE_NAME_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


@dataclass(frozen=True)
class JournalEntry:
    """1日分の日記を表す。"""

    journal_date: date
    markdown_text: str

    @property
    def excerpt(self) -> str:
        body = _extract_body_text(self.markdown_text)
        if len(body) <= 72:
            return body
        return f"{body[:72].rstrip()}..."


class JournalRepository:
    """日記ファイルの列挙と読み込みを担当する。"""

    def __init__(self, journals_dir: Path) -> None:
        self._journals_dir = journals_dir

    @property
    def journals_dir(self) -> Path:
        return self._journals_dir

    def list_entries(self, *, query: str = "") -> list[JournalEntry]:
        normalized_query = query.strip().lower()
        entries: list[JournalEntry] = []

        for target_date, file_path in self._iter_journal_files():
            markdown_text = file_path.read_text(encoding="utf-8-sig").strip()
            if normalized_query and normalized_query not in markdown_text.lower():
                continue
            entries.append(JournalEntry(journal_date=target_date, markdown_text=markdown_text))

        entries.sort(key=lambda item: item.journal_date, reverse=True)
        return entries

    def get_entry(self, target_date: date) -> JournalEntry | None:
        file_path = self._journals_dir / f"{target_date.isoformat()}.md"
        if not file_path.exists():
            return None
        markdown_text = file_path.read_text(encoding="utf-8-sig").strip()
        return JournalEntry(journal_date=target_date, markdown_text=markdown_text)

    def _iter_journal_files(self) -> list[tuple[date, Path]]:
        if not self._journals_dir.exists():
            return []

        files: list[tuple[date, Path]] = []
        for path in self._journals_dir.iterdir():
            if not path.is_file():
                continue
            match = _FILE_NAME_PATTERN.fullmatch(path.name)
            if match is None:
                continue
            files.append((date.fromisoformat(match.group(1)), path))
        return files


def parse_iso_date(raw_value: str) -> date:
    """YYYY-MM-DD 形式の日付文字列を検証して date に変換する。"""

    if not _FILE_NAME_PATTERN.fullmatch(f"{raw_value}.md"):
        raise ValueError("date must be YYYY-MM-DD")
    return date.fromisoformat(raw_value)


def resolve_prev_next_dates(
    entries: list[JournalEntry],
    current_date: date | None,
) -> tuple[date | None, date | None]:
    """現在日付に対する前日/翌日を返す（entries は新しい順）。"""

    if current_date is None:
        return None, None

    dates = [item.journal_date for item in entries]
    if current_date not in dates:
        return None, None

    index = dates.index(current_date)

    previous_date = dates[index + 1] if index + 1 < len(dates) else None
    next_date = dates[index - 1] if index - 1 >= 0 else None
    return previous_date, next_date


def _extract_body_text(markdown_text: str) -> str:
    lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
    if not lines:
        return "本文なし"

    first_line = lines[0]
    if re.fullmatch(r"(##\s*)?(\d{2}/\d{2}|\d{4}-\d{2}-\d{2})", first_line):
        lines = lines[1:]

    body = " ".join(lines).strip()
    return body if body else "本文なし"
