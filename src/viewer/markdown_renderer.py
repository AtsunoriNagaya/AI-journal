"""日記 Markdown の HTML 変換とサニタイズ。"""

import bleach
import markdown


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
    "a": ["href", "title", "target", "rel"],
}


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
    return bleach.linkify(clean_html)
