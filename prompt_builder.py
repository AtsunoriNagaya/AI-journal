from datetime import timedelta

from character_setting import JournalSetting


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

    return (
        "あなたは日記作家です。以下の条件で、1週間分の日記を日本語で作成してください。\n"
        f"- 期間: {dates}\n"
        f"- 主人公: {setting.role}\n"
        f"- 状況: {setting.background}\n"
        f"{incidents_text}\n"
        "- 各日: 日付見出し + おおむね400字（目安350〜450字）\n"
        "- 文字数は厳密一致不要だが、各日で大きく不足しない\n"
        "- 各日の文量バランスをそろえる\n"
        "- 新卒らしい学びと感情の変化を入れる\n"
        "- 読みやすい自然な文章にする"
    )
