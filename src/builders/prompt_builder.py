"""日記生成用プロンプトの構築モジュール。

責務:
    - JournalSetting から日別プロンプトを組み立てる
    - テンプレートに設定値を埋め込む
    - 日付計算とイベント情報の整形

このモジュールはプロンプト構築専任で、API 呼び出しやテンプレート読参は行わない。
テンプレート読込は prompt_templates.py に委譲する。
"""

from datetime import timedelta
from pathlib import Path

from src.input.character_setting import Incident, JournalSetting
from src.templates.prompt_templates import load_prompt_section


# prompts.md のパス（プロジェクトルートの config フォルダーを想定）
_PROMPTS_PATH = str(Path(__file__).parent.parent.parent / "config" / "prompts.md")


def build_dates(setting: JournalSetting) -> list[str]:
    """開始日と日数から日付見出し一覧を生成。

    Args:
        setting: 日記設定（開始日、日数を含む）。

    Returns:
        「04/01」「04/02」... 形式の日付文字列リスト。
    """
    return [
        (setting.start_date + timedelta(days=i)).strftime("%m/%d")
        for i in range(setting.days)
    ]


def build_day_prompt(setting: JournalSetting, day_number: int) -> str:
    """指定日の生成用プロンプトを構築。

    前日までの会話履歴を踏まえた、その日だけの日記生成を指示するプロンプト。

    Args:
        setting: 日記設定。
        day_number: 生成対象の日数（1-indexed、1日目は1）。

    Returns:
        「Daily User Prompt Template」に埋め込まれたプロンプト文字列。
    """
    date_text = (setting.start_date + timedelta(days=day_number - 1)).strftime("%m/%d")
    incident_text = _build_incident_text(setting.incidents, day_number)
    template = load_prompt_section("Daily User Prompt Template", _PROMPTS_PATH)
    return template.format(
        date=date_text,
        day_number=day_number,
        total_days=setting.days,
        role=setting.role,
        background=setting.background,
        incident_text=incident_text,
    )


def _build_incident_text(incidents: tuple[Incident, ...], day_number: int) -> str:
    """指定日のイベント内容をテキスト化。

    複数イベント がある場合は「/」で区切る。

    Args:
        incidents: すべてのイベント。
        day_number: 対象日（1-indexed）。

    Returns:
        その日のイベント説明文。複数の場合は「/」区切り、なしの場合は"特になし"。
    """
    matched = [incident.content for incident in incidents if incident.day == day_number]
    if not matched:
        return "特になし"
    if len(matched) == 1:
        return matched[0]
    return " / ".join(matched)
