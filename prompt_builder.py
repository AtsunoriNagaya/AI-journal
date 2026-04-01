from datetime import timedelta

from character_setting import JournalSetting
from prompt_templates import load_prompt_section


def build_dates(setting: JournalSetting) -> list[str]:
    return [
        (setting.start_date + timedelta(days=i)).strftime("%m/%d")
        for i in range(setting.days)
    ]


def build_prompt(setting: JournalSetting) -> str:
    dates = "、".join(build_dates(setting))
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
