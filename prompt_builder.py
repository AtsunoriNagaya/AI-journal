from datetime import timedelta

from character_setting import JournalSetting
from prompt_templates import load_prompt_section


# 開始日と日数から、見出し用の日付一覧を作る。
def build_dates(setting: JournalSetting) -> list[str]:
    return [
        (setting.start_date + timedelta(days=i)).strftime("%m/%d")
        for i in range(setting.days)
    ]


# 設定値をテンプレートに埋め込み、最終プロンプト文字列を作る。
def build_prompt(setting: JournalSetting) -> str:
    dates = "、".join(build_dates(setting))
    # イベント件数に応じて、プロンプトに渡す説明を切り替える。
    if not setting.incidents:
        incidents_text = "- イベント: 特になし"
    elif len(setting.incidents) == 1:
        inc = setting.incidents[0]
        incidents_text = f"- {inc.day}日目に{inc.content}"
    else:
        lines = [f"- {inc.day}日目: {inc.content}" for inc in setting.incidents]
        incidents_text = "- イベント一覧:\n" + "\n".join(lines)

    template = load_prompt_section("User Prompt Template")
    return template.format(
        dates=dates,
        role=setting.role,
        background=setting.background,
        incidents_text=incidents_text,
    )
