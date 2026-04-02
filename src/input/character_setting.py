"""キャラクター設定の読み込みと検証モジュール。

責務:
  - persona.md ファイルから日記ペルソナ情報を読み込む
  - 設定データの解析と検証
  - JournalSetting データクラスで型安全な表現を提供

このモジュールは入力の責務のみを持ち、生成処理には関わらない。
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re


# 1件の出来事を表すデータ。
@dataclass(frozen=True)
class Incident:
    day: int
    content: str


# 日記生成に必要な設定全体。
@dataclass(frozen=True)
class JournalSetting:
    start_date: date
    days: int
    role: str
    background: str
    incidents: tuple[Incident, ...]


# Markdown本文を「見出し -> 本文」の辞書に変換する。
def _parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        heading_match = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading_match:
            current_heading = heading_match.group(1).strip()
            sections.setdefault(current_heading, [])
            continue

        if current_heading is not None:
            sections[current_heading].append(line)

    return {key: "\n".join(value).strip() for key, value in sections.items()}


# 候補の見出し名から、最初に見つかった本文を返す。
def _pick_section(sections: dict[str, str], candidates: list[str]) -> str:
    for key in candidates:
        if key in sections and sections[key].strip():
            return sections[key].strip()
    names = ", ".join(candidates)
    raise ValueError(f"Markdown見出しが見つかりません: {names}")


# 期間セクションから開始日を抽出する。
def _extract_date(text: str) -> date:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if not match:
        raise ValueError("開始日(YYYY-MM-DD)が見つかりません")
    return date.fromisoformat(match.group(1))


# 期間セクションから日数を抽出する。
def _extract_days(text: str) -> int:
    match = re.search(r"(\d+)\s*日", text)
    if not match:
        raise ValueError("日数(例: 7日)が見つかりません")
    return int(match.group(1))


# イベントセクションから複数イベントを抽出する。
def _extract_incidents(text: str) -> tuple[Incident, ...]:
    incidents: list[Incident] = []
    current_day: int | None = None
    current_lines: list[str] = []

    # 現在バッファ中のイベントを1件として確定させる。
    def flush_current() -> None:
        nonlocal current_day, current_lines
        if current_day is None:
            return
        content = " ".join(current_lines).strip() or "出来事が発生"
        incidents.append(Incident(day=current_day, content=content))
        current_day = None
        current_lines = []

    for raw_line in text.splitlines():
        line = re.sub(r"^\s*[-*]\s*", "", raw_line).strip()
        if not line:
            continue

        day_match = re.search(r"(\d+)\s*日目", line)
        if day_match:
            flush_current()
            current_day = int(day_match.group(1))
            trailing = re.sub(r"^.*?\d+\s*日目\s*[:：]?\s*", "", line).strip()
            if trailing and trailing != "に発生":
                current_lines.append(trailing)
            continue

        if current_day is None:
            labeled = re.search(r"内容\s*[:：]\s*(.+)", line)
            if labeled:
                incidents.append(Incident(day=1, content=labeled.group(1).strip()))
                continue
            continue

        current_lines.append(line)

    flush_current()
    return tuple(incidents)


# すべてのイベント日が期間内か検証する。
def _validate_incidents(incidents: tuple[Incident, ...], days: int) -> None:
    for inc in incidents:
        if inc.day < 1 or inc.day > days:
            raise ValueError(
                f"イベント日が期間外です: {inc.day}日目 (期間は1日目〜{days}日目)"
            )


# persona.md から設定を読み込み、検証済みの JournalSetting を返す。
def load_setting_from_markdown(file_path: str = "persona.md") -> JournalSetting:
    text = Path(file_path).read_text(encoding="utf-8")

    sections = _parse_sections(text)
    role_text = _pick_section(sections, ["主人公", "キャラクター", "人物設定"])
    background_text = _pick_section(sections, ["状況", "背景"])
    period_text = _pick_section(sections, ["期間"])
    event_text = sections.get("イベント") or sections.get("出来事") or sections.get("インシデント", "")
    incidents = _extract_incidents(event_text)

    setting = JournalSetting(
        start_date=_extract_date(period_text),
        days=_extract_days(period_text),
        role=role_text.splitlines()[0].strip(),
        background=background_text.splitlines()[0].strip(),
        incidents=incidents,
    )
    _validate_incidents(setting.incidents, setting.days)
    return setting
