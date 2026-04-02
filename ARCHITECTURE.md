# AI Journal - アーキテクチャドキュメント

## 概要

このプロジェクトは、生成AI（OpenRouter API）を使用して、指定期間の日記を自動生成するツールです。日別ループとメモリを組み合わせて、過去との整合性がある出力を実現し、結果を stdout と Markdown ファイルに出力します。

## 責務分離

各モジュールは以下の責務を持ちます：

### 入力層（Input）
- **src/input/character_setting.py**
  - 責務: `config/persona.md` から設定を読み込み、型安全な `JournalSetting` オブジェクトに変換
  - 検証: 期間、イベント日数が有効範囲内か確認
  - 依存: なし（ファイル読み込みのみ）
  - アウトプット: `JournalSetting` データクラス

### テンプレート層（Template）
- **src/templates/prompt_templates.py**
  - 責務: `config/prompts.md` から Markdown セクションを効率的に読み込む
  - 管理: テンプレートセクション名の一元管理
  - 依存: なし（ファイル読み込みのみ）
  - アウトプット: テキスト文字列

### プロンプト生成層（Prompt Building）
- **src/builders/prompt_builder.py**
  - 責務: `JournalSetting` とテンプレートから日別プロンプトを生成
  - 処理: 日付計算、イベント情報の整形、変数埋め込み
  - 依存: `src/input/character_setting.py`、`src/templates/prompt_templates.py`
  - アウトプット: LLM に渡すプロンプト文字列

### 生成層（Generation）
- **src/generators/journal_generator.py**
  - 責務: OpenRouter API の呼び出し、LangChain チェーン管理、メモリ管理
  - 処理:
    - 環境変数から API 設定を読み込む
    - 日別ループでプロンプト実行
    - メモリに過去の出力を蓄積
    - `journals/YYYY-MM-DD.md` への日別保存
    - レート制限時の再試行
    - stdout への進捗出力
  - 依存: `src/builders/prompt_builder.py`、`src/templates/prompt_templates.py`（テンプレート読み込み）
  - アウトプット: 生成済みの日記本文

### 制御層（Main）
- **main.py**
  - 責務: 各モジュール間の連携を統制
  - フロー:
    1. 環境設定の初期化
    2. 入力の読み込みと検証
    3. 生成処理の実行
    4. エラーハンドリング
  - 依存: すべてのモジュール
  - アウトプット: 保存先ディレクトリ指定（`journals/`）

### 閲覧層（Web UI）
- **web_ui.py**
  - 責務: 生成済み Markdown の一覧・検索・詳細表示 API と HTML 画面を提供
  - 処理:
    - `journals/` から読み込み
    - 日付降順ソート
    - キーワード検索
    - 前日/翌日ナビゲーション
  - 依存: `src/viewer/journal_repository.py`、`src/viewer/markdown_renderer.py`
  - アウトプット: ブラウザ向け HTML と `/api/journals*` の JSON

- **src/viewer/journal_repository.py**
  - 責務: `journals/YYYY-MM-DD.md` の列挙・読み込み・検索・隣接日計算
  - 依存: なし（ファイル読み込みのみ）

- **src/viewer/markdown_renderer.py**
  - 責務: Markdown を HTML に変換し、許可タグのみ残す
  - 依存: markdown, bleach

- **src/viewer/comment_repository.py**
  - 責務: 日記ごとのコメント保存・読み込み（JSON）
  - 保存先: `journals/_comments/YYYY-MM-DD.json`（既定）
  - 依存: なし（ファイル読み込みのみ）

## スタック

- **Python 3.11+**: タイプセーフな実装、ジェネリクス対応
- **LangChain**: プロンプトテンプレート、チェーン構成、メモリ管理
- **OpenRouter API**: OpenAI 互換インタフェース、複数モデルのサポート
- **python-dotenv**: 環境変数管理

## データフロー

```
config/persona.md
  ↓
[src/input/character_setting.py] → JournalSetting
  ↓
[main.py]（実行を統制）
  ↓
[src/generators/journal_generator.py]
  ↓
[src/builders/prompt_builder.py] ← [src/templates/prompt_templates.py] ← config/prompts.md
  ↓
(日別プロンプト文字列)
  ↓
OpenRouter API
  ↓
stdout + journals/*.md → 日記本文
  ↓
[src/viewer/journal_repository.py] + [src/viewer/markdown_renderer.py]
  ↓
[web_ui.py] → HTML UI / JSON API
  ↓
comment_repository 経由でコメント投稿・表示
```

## 日別生成ループ

メモリベースの日別生成のシーケンス：

```
Day 1:
  Prompt → LLM → Output (1日目の日記)
  Output を stdout に流し、journals/2026-04-01.md へ保存
  メモリに ["1日目のテキスト"] を追加

Day 2:
  Prompt (with history) → LLM(前日を踏まえた状態で) → Output (2日目の日記)
  出力を stdout に流し、journals/2026-04-02.md へ保存
  メモリに ["1日目", "2日目"] を追加

...

Day 7:
  Prompt (with 6日分の履歴) → LLM → Output
  出力を stdout に流し、対応日付の Markdown に保存
```

## 拡張ポイント

新しい機能追加時の参考：

### 新しい出力形式（e.g., JSON）
- **追加場所**: `src/generators/journal_generator.py` の最終出力処理
- **注意**: メモリ層（LangChain）はテキストを扱うため、構造化データ化する場合は日別生成後に変換する

### コメント返信機能（将来拡張）
- **追加場所**: `web_ui.py` の API 層にコメント投稿エンドポイントを追加
- **注意**:
  - 初版では閲覧専用を維持し、生成フロー（`main.py` / `journal_generator.py`）とは分離する
  - コメント履歴は Markdown 追記ではなく、別ストレージ（JSON or SQLite）を検討する

### 新しい入力形式（e.g., YAML）
- **追加場所**: `src/input/character_setting.py` に新パーサーを追加
- **注意**: 出力は必ず `JournalSetting` か互換データクラスに変換

### 新しいテンプレート変数
- **追加方法**:
  1. `src/input/character_setting.py` に新フィールドを追加
  2. `src/builders/prompt_builder.py` で変数を埋め込み
  3. `config/prompts.md` で `{new_variable}` を使用

### ローカル実行時のデバッグ
- 環境変数 `AI_JOURNAL_MAX_RETRIES=0` で再試行を無効化
- 環境変数 `AI_JOURNAL_MAX_OUTPUT_TOKENS=300` で出力テスト

## エラー処理の責務

| エラー種類 | 処理層 | 対応 |
|-----------|--------|------|
| ファイル未検出 | `src/input/character_setting.py` | ValueError を送出（`main.py` で捕捉して終了） |
| パース失敗 | `src/input/character_setting.py` | ValueError を送出（`main.py` で捕捉して終了） |
| テンプレート未検出 | `src/templates/prompt_templates.py` | ValueError を送出（呼び出し元に伝播） |
| API キー未設定 | `src/generators/journal_generator.py` | RuntimeError |
| レート制限 | `src/generators/journal_generator.py` | 再試行 + 指数バックオフ |
| 日記生成失敗 | `main.py` | RuntimeError を catch して終了 |

## テスト戦略

各層は独立してテスト可能：

```python
# character_setting のテスト例
from src.input.character_setting import load_setting_from_markdown


def test_load_setting():
    setting = load_setting_from_markdown("config/persona.md")
    assert setting.days == 7
    assert len(setting.incidents) == 2

# prompt_builder のテスト例
from src.builders.prompt_builder import build_day_prompt


def test_build_day_prompt():
    prompt = build_day_prompt(setting, day_number=1)
    assert "04/01" in prompt
    assert setting.role in prompt
```

## 開発時の注意

- **ブレーキングチェンジ**: `JournalSetting` の構造変更は他すべてに影響するため、慎重に
- **テンプレート管理**: `config/prompts.md` のセクション名は `src/templates/prompt_templates.py` で参照される
- **環境変数**: `.env.example` はプロジェクトルートを正とする

## まとめ

- 各モジュールは1つの責務のみを持つ
- 依存関係は入力層 → テンプレート層/プロンプト生成層 → 生成層 → 制御層の順
- 新機能追加時はまず責務の分離を検討する
- テストは層ごとに独立して実施可能
