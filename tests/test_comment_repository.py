from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.viewer.comment_repository import CommentRepository


class CommentRepositoryTests(unittest.TestCase):
    def test_add_and_list_comments(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CommentRepository(Path(temp_dir))
            target_date = date(2026, 4, 7)

            repository.add_comment(target_date=target_date, author="太郎", body="1件目")
            repository.add_comment(target_date=target_date, author="", body="2件目")

            comments = repository.list_comments(target_date)
            self.assertEqual(len(comments), 2)
            self.assertEqual(comments[0].author, "太郎")
            self.assertEqual(comments[0].body, "1件目")
            self.assertEqual(comments[1].author, "匿名")

    def test_empty_body_is_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CommentRepository(Path(temp_dir))

            with self.assertRaises(ValueError):
                repository.add_comment(
                    target_date=date(2026, 4, 7),
                    author="",
                    body="   ",
                )

    def test_comments_are_isolated_by_date(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CommentRepository(Path(temp_dir))

            repository.add_comment(
                target_date=date(2026, 4, 6),
                author="A",
                body="6日目コメント",
            )
            repository.add_comment(
                target_date=date(2026, 4, 7),
                author="B",
                body="7日目コメント",
            )

            comments_day_6 = repository.list_comments(date(2026, 4, 6))
            comments_day_7 = repository.list_comments(date(2026, 4, 7))

            self.assertEqual(len(comments_day_6), 1)
            self.assertEqual(comments_day_6[0].body, "6日目コメント")
            self.assertEqual(len(comments_day_7), 1)
            self.assertEqual(comments_day_7[0].body, "7日目コメント")


if __name__ == "__main__":
    unittest.main()
