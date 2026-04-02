"""エントリーポイント。全体の実行フローを制御するモジュール。

責務:
  - 環境変数の初期化（.env の読み込み）
  - 各モジュールの連携と順序制御
  - エラーハンドリングとユーザーへのメッセージ

処理フロー:
  1. 環境設定の読み込み (dotenv)
  2. ペルソナ情報の取得 (character_setting)
  3. 日記生成の実行 (journal_generator)
     - 内部で prompt_builder と prompt_templates を使用
  4. 結果の出力と終了

このモジュールは処理の組立て役であり、各処理の詳細には関わらない。
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from src.input.character_setting import load_setting_from_markdown
from src.generators.journal_generator import generate_with_openrouter


# 設定読込 -> プロンプト生成 -> LLM実行 の順に処理する。
def main() -> None:
    # .env ファイルの位置を調整（プロジェクトルート）
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    # config/persona.md を読み込んで入力設定を作成する。
    persona_path = Path(__file__).parent / "config" / "persona.md"
    try:
        setting = load_setting_from_markdown(str(persona_path))
    except Exception as error:
        print(f"[ERROR] 設定ファイルの読み込みに失敗しました: {error}")
        sys.exit(1)

    # 生成に失敗した場合は内容を出さずエラーで終了する。
    try:
        generate_with_openrouter(setting)
    except Exception as error:
        print(f"[ERROR] 日記の生成に失敗しました: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
