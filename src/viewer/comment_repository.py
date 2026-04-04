"""日記ごとのコメント保存を扱うリポジトリ。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from threading import Lock
from uuid import uuid4


_DEFAULT_AUTHOR = "匿名"
_MAX_AUTHOR_LENGTH = 40
_MAX_BODY_LENGTH = 1000
_ROLE_USER = "user"
_ROLE_PERSONA = "persona"
_VALID_ROLES = {_ROLE_USER, _ROLE_PERSONA}


@dataclass(frozen=True)
class JournalComment:
    """1件のコメント。"""

    comment_id: str
    journal_date: date
    author: str
    role: str
    body: str
    created_at: datetime

    @property
    def created_at_iso(self) -> str:
        return self.created_at.isoformat()

    @property
    def created_at_label(self) -> str:
        return self.created_at.astimezone().strftime("%Y-%m-%d %H:%M")


class CommentRepository:
    """コメントの読み書きを行う（プロセス内メモリ保持）。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._comments_by_date: dict[date, list[JournalComment]] = {}

    def list_comments(self, target_date: date) -> list[JournalComment]:
        with self._lock:
            comments = list(self._comments_by_date.get(target_date, []))
        return sorted(comments, key=lambda item: item.created_at)

    def add_comment(
        self,
        *,
        target_date: date,
        author: str,
        role: str = _ROLE_USER,
        body: str,
    ) -> JournalComment:
        normalized_author = _normalize_author(author)
        normalized_role = _normalize_role(role)
        normalized_body = _normalize_body(body)

        comment = JournalComment(
            comment_id=uuid4().hex,
            journal_date=target_date,
            author=normalized_author,
            role=normalized_role,
            body=normalized_body,
            created_at=datetime.now(timezone.utc).replace(microsecond=0),
        )

        with self._lock:
            self._comments_by_date.setdefault(target_date, []).append(comment)

        return comment


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


def _normalize_role(raw_role: str) -> str:
    role = raw_role.strip().lower()
    if role in _VALID_ROLES:
        return role
    return _ROLE_USER
