import sys

from dotenv import load_dotenv
from character_setting import load_setting_from_markdown
from journal_generator import generate_with_openrouter
from prompt_builder import build_prompt


# 設定読込 -> プロンプト生成 -> LLM実行 の順に処理する。
def main() -> None:
    load_dotenv()

    # persona.md を読み込んで入力設定を作成する。
    try:
        setting = load_setting_from_markdown()
    except Exception as error:
        print(f"[ERROR] 設定ファイルの読み込みに失敗しました: {error}")
        sys.exit(1)

    prompt = build_prompt(setting)

    # 生成に失敗した場合は内容を出さずエラーで終了する。
    try:
        diary = generate_with_openrouter(prompt)
    except Exception as error:
        print(f"[ERROR] 日記の生成に失敗しました: {error}")
        sys.exit(1)

    print(diary)


if __name__ == "__main__":
    main()
