"""日記ごとのコメント保存を扱うリポジトリ。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


_DEFAULT_AUTHOR = "匿名"
_MAX_AUTHOR_LENGTH = 40
_MAX_BODY_LENGTH = 1000


@dataclass(frozen=True)
class JournalComment:
    """1件のコメント。"""

    comment_id: str
    journal_date: date
    author: str
    body: str
    created_at: datetime

    @property
    def created_at_iso(self) -> str:
        return self.created_at.isoformat()

    @property
    def created_at_label(self) -> str:
        return self.created_at.astimezone().strftime("%Y-%m-%d %H:%M")


class CommentRepository:
    """コメントの読み書きを行う。"""

    def __init__(self, comments_dir: Path) -> None:
        self._comments_dir = comments_dir

    @property
    def comments_dir(self) -> Path:
        return self._comments_dir

    def list_comments(self, target_date: date) -> list[JournalComment]:
        payload = self._load_payload(self._comment_file_path(target_date))

        comments: list[JournalComment] = []
        for item in payload:
            parsed = _deserialize_comment_item(item, target_date)
            if parsed is not None:
                comments.append(parsed)

        comments.sort(key=lambda item: item.created_at)
        return comments

    def add_comment(
        self,
        *,
        target_date: date,
        author: str,
        body: str,
    ) -> JournalComment:
        normalized_author = _normalize_author(author)
        normalized_body = _normalize_body(body)

        comment = JournalComment(
            comment_id=uuid4().hex,
            journal_date=target_date,
            author=normalized_author,
            body=normalized_body,
            created_at=datetime.now(timezone.utc).replace(microsecond=0),
        )

        path = self._comment_file_path(target_date)
        payload = self._load_payload(path)
        payload.append(_serialize_comment_item(comment))
        self._save_payload(path, payload)

        return comment

    def _comment_file_path(self, target_date: date) -> Path:
        return self._comments_dir / f"{target_date.isoformat()}.json"

    def _load_payload(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        raw_text = path.read_text(encoding="utf-8")
        if not raw_text.strip():
            return []

        loaded = json.loads(raw_text)
        if not isinstance(loaded, list):
            raise ValueError(f"invalid comment store format: {path}")

        valid_items: list[dict[str, Any]] = []
        for item in loaded:
            if isinstance(item, dict):
                valid_items.append(item)
        return valid_items

    def _save_payload(self, path: Path, payload: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)


def _normalize_author(raw_author: str) -> str:
    author = " ".join(raw_author.strip().split())
    if not author:
        return _DEFAULT_AUTHOR
    if len(author) > _MAX_AUTHOR_LENGTH:
        return author[:_MAX_AUTHOR_LENGTH]
    return author


def _normalize_body(raw_body: str) -> str:
    body = raw_body.replace("\r\n", "\n").strip()
    if not body:
        raise ValueError("コメント本文を入力してください")
    if len(body) > _MAX_BODY_LENGTH:
        raise ValueError(f"コメント本文は{_MAX_BODY_LENGTH}文字以内で入力してください")
    return body


def _serialize_comment_item(comment: JournalComment) -> dict[str, str]:
    return {
        "id": comment.comment_id,
        "author": comment.author,
        "body": comment.body,
        "created_at": comment.created_at_iso,
    }


def _deserialize_comment_item(item: dict[str, Any], target_date: date) -> JournalComment | None:
    raw_body = item.get("body")
    if not isinstance(raw_body, str):
        return None

    raw_created_at = item.get("created_at")
    if not isinstance(raw_created_at, str):
        return None

    try:
        created_at = datetime.fromisoformat(raw_created_at)
    except ValueError:
        return None

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    raw_author = item.get("author", "")
    author = _normalize_author(raw_author) if isinstance(raw_author, str) else _DEFAULT_AUTHOR

    raw_comment_id = item.get("id")
    comment_id = str(raw_comment_id).strip() if raw_comment_id else uuid4().hex

    return JournalComment(
        comment_id=comment_id,
        journal_date=target_date,
        author=author,
        body=raw_body,
        created_at=created_at,
    )
