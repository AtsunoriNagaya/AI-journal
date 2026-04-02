# AI Journal - アーキテクチャドキュメント

## 概要

このプロジェクトは、生成AI（OpenRouter API）を使用して、指定日期間の日記を自動生成するツールです。日別ルームとメモリを使用して、過去の日記を踏まえた一貫性のある出力を実現します。

## 責務分離

各モジュールは以下の責務を持ちます：

### 入力層（Input）
- **character_setting.py**
  - 責務: `persona.md` から設定を読み込み、型安全な `JournalSetting` オブジェクトに変換
  - 検証: 期間、イベント日数が有効範囲内か確認
  - 依存: なし（ファイル読み込みのみ）
  - アウトプット: `JournalSetting` データクラス

### テンプレート層（Template）
- **prompt_templates.py**
  - 責務: `prompts.md` から Markdown セクションを効率的に読み込む
  - 管理: テンプレートセクション名の一元管理
  - 依存: なし（ファイル読み込みのみ）
  - アウトプット: テキスト文字列

### プロンプト生成層（Prompt Building）
- **prompt_builder.py**
  - 責務: `JournalSetting` とテンプレートから日別プロンプトを生成
  - 処理: 日付計算、イベント情報の整形、変数埋め込み
  - 依存: `character_setting.py`、`prompt_templates.py`
  - アウトプット: LLM に渡すプロンプト文字列

### 生成層（Generation）
- **journal_generator.py**
  - 責務: OpenRouter API の呼び出し、LangChain チェーン管理、メモリ管理
  - 処理:
    - 環境変数から API 設定を読み込む
    - 日別ループでプロンプト実行
    - メモリに従来の出力を蓄積
    - レート制限時の再試行、モデルフォールバック
    - stdout への進捗出力
  - 依存: `prompt_builder.py`、`prompt_templates.py`（テンプレート読み込み）
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
  - アウトプット: なし（結果は stdout に流される）

## スタック

- **Python 3.11+**: タイプセーフな実装、ジェネリクス対応
- **LangChain**: プロンプトテンプレート、チェーン構成、メモリ管理
- **OpenRouter API**: OpenAI 互換インタフェース、複数モデルのサポート
- **python-dotenv**: 環境変数管理

## データフロー

```
persona.md
    ↓
[character_setting.py] → JournalSetting
                              ↓
                         [main.py]
                          ↓    ↓
                          ↓    └→ [journal_generator.py]
                          ↓              ↓
prompts.md     ↓         ↓
    ↓          └→ [prompt_templates.py]     ↓
    ↓                     ↓
    └─────────────→ [prompt_builder.py] ────┘
                          ↓
                    (プロンプト文字列)
                          ↓
                    OpenRouter API
                          ↓
                    stdout → 日記本文
```

## 日別生成ループ

メモリベースの日別生成のシーケンス：

```
Day 1:
  Prompt → LLM → Output (1日目の日記)
  Output を stdout に流す
  メモリに ["1日目のテキスト"] を追加

Day 2:
  Prompt (with history) → LLM(前日を踏まえた状態で) → Output (2日目の日記)
  出力を stdout に流す
  メモリに ["1日目", "2日目"] を追加

...

Day 7:
  Prompt (with 6日分の履歴) → LLM → Output
  出力を stdout に流す
```

## 拡張ポイント

新しい機能追加時の参考：

### 新しい出力形式（e.g., JSON）
- **追加場所**: `journal_generator.py` の最後で戻り値の形式変更
- **注意**: メモリ層（LangChain）はテキストのみ対応のため、`_generate_with_history()` の出力処理を別にする

### 新しい入力形式（e.g., YAML）
- **追加場所**: `character_setting.py` に新パーサーを追加
- **注意**: 出力は必ず `JournalSetting` か互換データクラスに変換

### 新しいテンプレート変数
- **追加方法**:
  1. `character_setting.py` に新フィールドを追加
  2. `prompt_builder.py` で変数を埋め込み
  3. `prompts.md` で `{new_variable}` を使用

### ローカル実行時のデバッグ
- 環境変数 `AI_JOURNAL_MAX_RETRIES=0` で再試行を無効化
- 環境変数 `AI_JOURNAL_MAX_OUTPUT_TOKENS=300` で出力テスト

## エラー処理の責務

| エラー種類 | 처리層 | 対応 |
|-----------|--------|------|
| ファイル未検出 | `character_setting.py` | ValueError + sys.exit(1) |
| パース失敗 | `character_setting.py` | ValueError + sys.exit(1) |
| テンプレート未検出 | `prompt_templates.py` | ValueError（呼び出し元で処理） |
| API キー未設定 | `journal_generator.py` | RuntimeError |
| モデル未提供 | `journal_generator.py` | 재시도 → RuntimeError |
| 429 レート制限 | `journal_generator.py` | 재시도 + 지수 백オフ |
| 日記生成失敗 | `main.py` | RuntimeError を catch して終了 |

## テスト戦略

各層は独立してテスト可能：

```python
# character_setting のテスト例
def test_load_setting():
    setting = load_setting_from_markdown("test_persona.md")
    assert setting.days == 7
    assert len(setting.incidents) == 2

# prompt_builder のテスト例
def test_build_day_prompt():
    prompt = build_day_prompt(setting, day_number=1)
    assert "04/01" in prompt
    assert setting.role in prompt
```

## 開発時の注意

- **ブレーキングチェンジ**: `JournalSetting` の構造変更は他すべてに影響するため、慎重に
- **テンプレート管理**: `prompts.md` のセクション名は `prompt_templates.py` で参照される
- **環境変数**: `.env.example` を追加して初期化例を明確に

## まとめ

- 各モジュールは1つの責務のみを持つ
- 依存関係は入力層 → 生成層 → 制御層の順
- 新機能追加時はまず責務の分離を検討す
- テストは層ごとに独立して実施可能
