import sys

from dotenv import load_dotenv
from character_setting import load_setting_from_markdown
from journal_generator import generate_with_gemini
from prompt_builder import build_prompt


def main() -> None:
    load_dotenv()

    try:
        setting = load_setting_from_markdown()
    except Exception as error:
        print(f"[ERROR] 設定ファイルの読み込みに失敗しました: {error}")
        sys.exit(1)

    prompt = build_prompt(setting)

    try:
        diary = generate_with_gemini(prompt)
    except Exception as error:
        print(f"[ERROR] 日記の生成に失敗しました: {error}")
        sys.exit(1)

    print(diary)


if __name__ == "__main__":
    main()
