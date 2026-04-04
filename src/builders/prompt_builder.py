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
from src.utils.text_utils import compact_text


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


def build_day_prompt(
    setting: JournalSetting,
    day_number: int,
    previous_summary: str = "",
    avoid_repetition_hint: str = "",
) -> str:
    """指定日の生成用プロンプトを構築。

    前日までの会話履歴を踏まえた、その日だけの日記生成を指示するプロンプト。

    Args:
        setting: 日記設定。
        day_number: 生成対象の日数（1-indexed、1日目は1）。
        previous_summary: 前日までの短い要約。空の場合は既定文を使う。
        avoid_repetition_hint: 直近で使いすぎた要素の回避ヒント。

    Returns:
        「Daily User Prompt Template」に埋め込まれたプロンプト文字列。
    """
    target_date = setting.start_date + timedelta(days=day_number - 1)
    date_text = target_date.strftime("%m/%d")
    day_mode = "平日" if target_date.weekday() < 5 else "休日"
    fixed_event_today = _build_incident_text(setting.incidents, day_number)
    summary_text = previous_summary.strip() or "- まだ前日までの記録はありません（1日目）。"
    avoid_hint = avoid_repetition_hint.strip() or "なし"
    structure_hint = _pick_structure_hint(day_number, day_mode)
    uniqueness_hint = _build_uniqueness_hint(setting)
    template = load_prompt_section("Daily User Prompt Template", _PROMPTS_PATH)
    return template.format(
        persona_block=_build_persona_block(setting),
        date=date_text,
        day_number=day_number,
        total_days=setting.days,
        day_mode=day_mode,
        fixed_event_today=fixed_event_today,
        previous_summary=summary_text,
        avoid_repetition_hint=avoid_hint,
        structure_hint=structure_hint,
        uniqueness_hint=uniqueness_hint,
    )


def _build_persona_block(setting: JournalSetting) -> str:
    """JournalSetting の主要項目を箇条書きブロックへ変換する。"""
    # label と値をペアで管理しておくと、項目追加時に 1 行で追記できる。
    fields = (
        ("主人公", setting.role),
        ("背景", setting.background),
        ("1週間のテーマ", setting.weekly_theme),
        ("平日傾向", setting.weekday_style),
        ("休日傾向", setting.weekend_style),
        ("文体", setting.tone_keywords),
        ("想定読者", setting.target_reader),
        ("現実味の制約", setting.realism_constraints),
        ("よく使う行動範囲", setting.living_area),
        ("興味・趣味", setting.hobbies),
        ("不安や悩み", setting.concerns),
        ("日常で起こりやすいこと", setting.likely_events),
        ("避けたい展開", setting.avoid_patterns),
        ("1週間を通して見せたい変化", setting.growth_direction),
    )
    return "\n".join(
        # テンプレート埋め込み前に空白を正規化し、不要な改行差分を防ぐ。
        f"- {label}: {_compact_text(value)}"
        for label, value in fields
    )


def _compact_text(text: str) -> str:
    """テンプレート向けに空白を 1 つへ畳み込む。"""
    return compact_text(text)


def _pick_structure_hint(day_number: int, day_mode: str) -> str:
    """日数と平日/休日に応じて構成ヒントをローテーション選択する。"""
    weekday_patterns = [
        "導入はその日の小さな違和感や引っかかりから始める",
        "導入は短い会話、通知、音など外部のきっかけから始める",
        "導入は身体感覚や生活リズムの乱れから始め、気分の変化を軸にする",
        "導入は小さな失敗や迷いから始め、対処の過程を中心に描く",
    ]
    weekend_patterns = [
        "導入は部屋の様子や家事など生活の手触りから始める",
        "導入は外出先または身近な風景の短い観察から始める",
        "導入は休息や趣味の場面から始め、次の日への小さな持ち越しで閉じる",
    ]

    # 同じ型の導入が連続しすぎないよう、日数で循環させる。
    patterns = weekend_patterns if day_mode == "休日" else weekday_patterns
    return patterns[(day_number - 1) % len(patterns)]


def _build_uniqueness_hint(setting: JournalSetting) -> str:
    """日ごとの差異を出すための補助ヒント文を作る。"""
    return (
        "補足設定のうち、行動範囲・趣味・不安や悩み・変化方向から1つ選び、"
        "その日の一場面に自然ににじませる。"
        f"候補: 行動範囲（{_compact_text(setting.living_area)}） / 趣味（{_compact_text(setting.hobbies)}） / "
        f"不安（{_compact_text(setting.concerns)}） / 変化方向（{_compact_text(setting.growth_direction)}）"
    )


def _build_incident_text(incidents: tuple[Incident, ...], day_number: int) -> str:
    """指定日のイベント内容をテキスト化。

    複数イベント がある場合は「/」で区切る。

    Args:
        incidents: すべてのイベント。
        day_number: 対象日（1-indexed）。

    Returns:
        その日のイベント説明文。複数の場合は「/」区切り、なしの場合は"なし"。
    """
    matched = [incident.content for incident in incidents if incident.day == day_number]
    if not matched:
        return "なし"
    if len(matched) == 1:
        return matched[0]
    return " / ".join(matched)
