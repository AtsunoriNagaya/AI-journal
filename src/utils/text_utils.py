"""テキスト整形ヘルパー。"""

import re


_WHITESPACE_PATTERN = re.compile(r"\s+")


def compact_text(text: str) -> str:
    """連続した空白・改行を 1 つの半角スペースに畳み込む。"""
    # \s+ は改行・タブ・全角/半角スペースの連続をまとめて検出する。
    # テンプレート差し込み前に正規化しておくと、見た目の揺れを抑えられる。
    return _WHITESPACE_PATTERN.sub(" ", text).strip()