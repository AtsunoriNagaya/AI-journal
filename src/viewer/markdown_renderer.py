"""日記 Markdown の HTML 変換とサニタイズ。"""

import bleach
import markdown
from bleach.linkifier import DEFAULT_CALLBACKS


_ALLOWED_TAGS = [
    "p",
    "br",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "code",
    "pre",
    "a",
]

_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel"],
}


def _enforce_safe_rel(attrs: dict[tuple[str | None, str], str], new: bool = False):
    href_key = (None, "href")
    if href_key not in attrs:
        return attrs

    rel_key = (None, "rel")
    existing_rel = attrs.get(rel_key, "")
    rel_tokens = {token for token in existing_rel.split() if token}
    rel_tokens.update({"nofollow", "noopener", "noreferrer"})
    attrs[rel_key] = " ".join(sorted(rel_tokens))
    return attrs


def render_markdown_html(markdown_text: str) -> str:
    """Markdown を HTML に変換し、安全なタグのみ残す。"""

    raw_html = markdown.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "nl2br"],
    )
    clean_html = bleach.clean(
        raw_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=["http", "https", "mailto"],
        strip=True,
    )
    return bleach.linkify(clean_html, callbacks=[*DEFAULT_CALLBACKS, _enforce_safe_rel])
