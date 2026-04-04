from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.viewer.journal_repository import (
    JournalRepository,
    parse_iso_date,
    resolve_prev_next_dates,
)


class JournalRepositoryTests(unittest.TestCase):
    def test_list_entries_sorts_desc_and_ignores_irrelevant_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            journals_dir = Path(temp_dir)
            (journals_dir / "2026-04-05.md").write_text("5日目", encoding="utf-8")
            (journals_dir / "2026-04-07.md").write_text("7日目", encoding="utf-8")
            (journals_dir / "memo.txt").write_text("ignore", encoding="utf-8")
            (journals_dir / "2026-04-xx.md").write_text("ignore", encoding="utf-8")

            repo = JournalRepository(journals_dir)
            entries = repo.list_entries()

            self.assertEqual([item.journal_date.isoformat() for item in entries], [
                "2026-04-07",
                "2026-04-05",
            ])

    def test_list_entries_filters_by_keyword(self) -> None:
        with TemporaryDirectory() as temp_dir:
            journals_dir = Path(temp_dir)
            (journals_dir / "2026-04-05.md").write_text("予定変更が起きた", encoding="utf-8")
            (journals_dir / "2026-04-06.md").write_text("静かな散歩をした", encoding="utf-8")

            repo = JournalRepository(journals_dir)
            entries = repo.list_entries(query="予定")

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].journal_date.isoformat(), "2026-04-05")

    def test_resolve_prev_next_dates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            journals_dir = Path(temp_dir)
            (journals_dir / "2026-04-05.md").write_text("5日目", encoding="utf-8")
            (journals_dir / "2026-04-06.md").write_text("6日目", encoding="utf-8")
            (journals_dir / "2026-04-07.md").write_text("7日目", encoding="utf-8")

            repo = JournalRepository(journals_dir)
            entries = repo.list_entries()

            previous_date, next_date = resolve_prev_next_dates(entries, date(2026, 4, 6))
            self.assertEqual(previous_date, date(2026, 4, 5))
            self.assertEqual(next_date, date(2026, 4, 7))

            previous_date, next_date = resolve_prev_next_dates(entries, date(2026, 4, 7))
            self.assertEqual(previous_date, date(2026, 4, 6))
            self.assertIsNone(next_date)

    def test_parse_iso_date_rejects_invalid_format(self) -> None:
        with self.assertRaises(ValueError):
            parse_iso_date("2026/04/07")

    def test_invalid_calendar_date_filename_is_skipped(self) -> None:
        with TemporaryDirectory() as temp_dir:
            journals_dir = Path(temp_dir)
            (journals_dir / "2026-04-07.md").write_text("有効", encoding="utf-8")
            (journals_dir / "2026-13-01.md").write_text("無効", encoding="utf-8")

            repo = JournalRepository(journals_dir)
            entries = repo.list_entries()

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].journal_date.isoformat(), "2026-04-07")

    def test_leading_whitespace_is_preserved_for_markdown(self) -> None:
        with TemporaryDirectory() as temp_dir:
            journals_dir = Path(temp_dir)
            content = "    code line\n"
            (journals_dir / "2026-04-07.md").write_text(content, encoding="utf-8")

            repo = JournalRepository(journals_dir)
            entry = repo.get_entry(date(2026, 4, 7))

            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertEqual(entry.markdown_text, content)


if __name__ == "__main__":
    unittest.main()
