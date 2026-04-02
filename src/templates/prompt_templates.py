"""Markdown テンプレートの読み込みモジュール。

責務:
  - prompts.md から Markdown 見出しで整理されたテンプレートを読み込む
  - セクション別の効率的な検索と取得
  - エラー時の有用なメッセージ提示

このモジュールはファイル I/O と文字列パース専門。LLM や生成処理には関わらない。
"""

from pathlib import Path
import re


# prompts.md から指定見出しの本文を読み込む。
def load_prompt_section(section_name: str, file_path: str = "prompts.md") -> str:
    # UTF-8 BOM 付きファイルでも先頭見出しを正しく読めるようにする
    text = Path(file_path).read_text(encoding="utf-8-sig")
    pattern = re.compile(r"^#{1,6}\s+(.+)$")

    sections: dict[str, list[str]] = {}
    current_heading: str | None = None

    # Markdownを見出し単位で分割して辞書化する。
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        heading_match = pattern.match(line)
        if heading_match:
            current_heading = heading_match.group(1).strip()
            sections.setdefault(current_heading, [])
            continue

        if current_heading is not None:
            sections[current_heading].append(line)

    if section_name not in sections:
        raise ValueError(f"Prompt section not found in {file_path}: {section_name}")

    content = "\n".join(sections[section_name]).strip()
    if not content:
        raise ValueError(f"Prompt section is empty in {file_path}: {section_name}")

    return content
