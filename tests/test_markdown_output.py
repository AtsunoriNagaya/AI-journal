from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.generators.journal_generator import _save_day_diary_markdown


class SaveDayDiaryMarkdownTests(unittest.TestCase):
    def test_create_markdown_file_with_iso_date_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "journals"

            output_path = _save_day_diary_markdown(
                output_dir=output_dir,
                start_date=date(2026, 4, 1),
                day_number=2,
                diary_text="2日目の本文",
            )

            self.assertIsNotNone(output_path)
            self.assertEqual(output_path, output_dir / "2026-04-02.md")
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "2日目の本文")

    def test_overwrite_existing_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "journals"
            output_dir.mkdir(parents=True, exist_ok=True)
            target_file = output_dir / "2026-04-01.md"
            target_file.write_text("古い本文", encoding="utf-8")

            _save_day_diary_markdown(
                output_dir=output_dir,
                start_date=date(2026, 4, 1),
                day_number=1,
                diary_text="新しい本文",
            )

            self.assertEqual(target_file.read_text(encoding="utf-8"), "新しい本文")

    def test_skip_save_when_output_dir_is_none(self) -> None:
        output_path = _save_day_diary_markdown(
            output_dir=None,
            start_date=date(2026, 4, 1),
            day_number=1,
            diary_text="保存されない本文",
        )

        self.assertIsNone(output_path)


if __name__ == "__main__":
    unittest.main()
