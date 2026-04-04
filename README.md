# AI Journal

生成AI（OpenRouter API）を使用して、1週間の一貫性のある日記を自動生成するツール。日別ループと会話履歴を使い、前日との整合性を保ちながら1日ずつ本文を生成します。

## クイックスタート

### 必要な環境
- Python 3.11+
- uv（パッケージマネージャー）

### セットアップ

```bash
# 環境変数の設定
cp .env.example .env
# （プロジェクトルートに作成された）.env に OpenRouter API キーを記入

# 依存関係のインストール
uv sync

# ペルソナ設定を編集
# config/persona.md を編集して、生成対象の人物・期間・イベント情報を記入

# 実行
uv run main.py
```

### 出力
- stdout に日付見出し付きの日記が1日ずつリアルタイムで出力されます
- 同時に `journals/YYYY-MM-DD.md` へ1日ずつ保存されます（同日付は上書き）

stdout の例：

```
04/01
<1日目の日記（約380〜420字）>

04/02
<2日目の日記（約380〜420字）>

...
```

保存ファイルの例：

```text
journals/
   2026-04-01.md
   2026-04-02.md
   ...
```

## Web UIで確認する

生成済みの日記をブラウザで確認できます。

```bash
uv run uvicorn web_ui:app --reload
```

起動後、`http://127.0.0.1:8000` を開いてください。

初版の機能：
- 日付一覧（新しい順）
- Markdown の整形表示
- 本文キーワード検索
- 前日/翌日への移動
- 日記ごとのコメント投稿・表示
- コメント投稿時のペルソナ自動返信
- スマホ表示対応

API 例：
- `GET /api/journals?q=通信`（一覧・検索）
- `GET /api/journals/2026-04-07`（詳細）

コメントの保存方式：
- コメントは Web UI プロセス内メモリに保持されます
- サーバー再起動（`uvicorn` 再起動）でコメントはリセットされます

ペルソナ返信の設定：
- `OPENROUTER_API_KEY` を設定しておくと、コメント投稿時に `config/persona.md` の主人公として返信が生成されます
- 返信に使うペルソナファイルは `AI_JOURNAL_PERSONA_PATH` で変更できます

## 設定方法

### ペルソナ設定（config/persona.md）

注意:
- 見出し名は固定です（後方互換の別名見出しは廃止）。
- 必須見出し: `主人公` / `背景` / `期間` / `1週間のテーマ` / `平日傾向` / `休日傾向` / `文体` / `想定読者` / `現実味の制約` / `補足設定`
- `補足設定` は次の6項目すべてが必須です。
   - よく使う行動範囲
   - 興味・趣味
   - 不安や悩み
   - 日常で起こりやすいこと
   - 避けたい展開
   - 1週間を通して見せたい変化

```markdown
## 主人公
新卒のエンジニア（開発未経験）

## 背景
コロナ禍で外出自粛が続く

## 期間
開始日 2026-04-01
7日間

## 1週間のテーマ
不安定な通信環境のなかで、少しずつ仕事に慣れていく

## 平日傾向
仕事、通勤、オンライン会議、昼休み、同僚とのやり取りを中心にする

## 休日傾向
家での休息、買い物、軽い気分転換、生活の整え直しを中心にする

## 文体
自然体、やわらかい、読みやすい

## 想定読者
同じように日常を積み重ねる読者

## 現実味の制約
主人公の生活圏で起こりうる出来事に限定し、過剰な偶然や大事件は避ける

## イベント（任意）
2日目に発生
通信障害
```

### プロンプト設定（config/prompts.md）

- `# System Prompt`: LLM への共通指示（系統的な指示）
- `# Common Guidelines`: 全日共通のガイドライン
- `# Daily User Prompt Template`: 日別プロンプトテンプレート
   - 使用可能な変数: `{persona_block}`, `{date}`, `{day_number}`, `{total_days}`, `{day_mode}`, `{fixed_event_today}`, `{previous_summary}`, `{structure_hint}`, `{uniqueness_hint}`, `{avoid_repetition_hint}`
- `# Daily Prompt Default Previous Summary`: 1日目の既定要約文
- `# Daily Prompt Default Avoid Repetition Hint`: 重複回避ヒント未指定時の既定文
- `# Weekday Structure Hints` / `# Weekend Structure Hints`: 日別の構成ヒント候補
- `# Uniqueness Hint Template`: 固有性ヒント文のテンプレート
- `# Persona Reply System Prompt`: コメント返信の system プロンプト
- `# Persona Reply User Prompt Template`: コメント返信の user プロンプト
- `# Persona Reply Empty History`: 会話履歴が空のときの表示文

### 環境変数設定（.env）

環境変数の一覧と説明は [.env.example](.env.example) を正本にしています。
値を追加・変更するときは、`.env` だけでなく `.env.example` も更新してください。

最小構成の例:

```env
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_MODEL=qwen/qwen3.6-plus:free
```

補足:
- コメント返信の再試行回数は `AI_PERSONA_MAX_RETRIES` のみ参照します。
- `AI_JOURNAL_MAX_RETRIES` へのフォールバックは廃止されています。

## ファイル構成

| ファイル | 責務 |
|---------|------|
| **main.py** | エントリーポイント・全体フロー制御 |
| **src/input/character_setting.py** | config/persona.md の読み込みと検証 |
| **src/templates/prompt_templates.py** | config/prompts.md のテンプレート読み込み |
| **src/builders/prompt_builder.py** | 日別プロンプトの生成 |
| **src/generators/journal_generator.py** | OpenRouter API 呼び出し・メモリ管理 |
| **src/utils/env_utils.py** | 環境変数の共通パーサー |
| **src/utils/text_utils.py** | 文字列の空白正規化ヘルパー |
| **src/viewer/journal_repository.py** | journals/ の日記読み込み・検索・日付移動計算 |
| **src/viewer/comment_repository.py** | 日記ごとのコメントをメモリ保持（再起動でリセット） |
| **src/viewer/persona_reply_service.py** | コメントへのペルソナ返信を生成 |
| **src/viewer/markdown_renderer.py** | Markdown を安全な HTML に変換 |
| **web_ui.py** | FastAPI ベースの閲覧 UI エントリーポイント |
| **webapp/templates/index.html** | 閲覧画面テンプレート |
| **webapp/static/styles.css** | 閲覧画面のスタイル |
| **config/persona.md** | ペルソナ・期間・固定条件の定義 |
| **config/prompts.md** | System・共通・日別プロンプトテンプレート |
| **ARCHITECTURE.md** | 詳細な責務と拡張ガイド |

## アーキテクチャ

責務ごとに層を分離しています。詳細は [ARCHITECTURE.md](ARCHITECTURE.md) を参照ください。

```
入力層 (character_setting)
   ↓
テンプレート層 (prompt_templates)
   ↓
プロンプト生成層 (prompt_builder)
   ↓
生成層 (journal_generator)
   └─ メモリベースの日別ループで本文生成
   ↓
制御層 (main) ← エラーハンドリング
   ↓
stdout + journals/*.md → 日記本文
```

## トラブルシューティング

### API キーエラー
```
[ERROR] 設定ファイルの読み込みに失敗しました: OPENROUTER_API_KEY is not set
```
→ .env に `OPENROUTER_API_KEY` を追加してください

### モデル利用不可エラー
```
[ERROR] 日記の生成に失敗しました: OpenRouter のレート制限またはモデル未提供...
```
→ 少し時間をおいて再実行してください。フォールバック機能は廃止済みのため、モデル切り替えは `OPENROUTER_MODEL` の変更で行います

### 日記が短すぎる
→ config/prompts.md の `# Daily User Prompt Template` で「おおむね400字」を「おおむね450字」に変更するか、`AI_JOURNAL_MAX_OUTPUT_TOKENS` を上げてください

## 拡張開発ガイド

新しい機能を追加する前に、[ARCHITECTURE.md](ARCHITECTURE.md) の「拡張ポイント」セクションを確認ください。

### よくある拡張例

**新しい入力形式（YAML など）を追加**
- src/input/character_setting.py に新パーサーを追加
- 出力は `JournalSetting` に統一

**デバッグ出力を追加**
- main.py に `--debug` フラグを追加し、中間プロンプトを表示

**ローカルモデル（Ollama など）に切り替え**
- src/generators/journal_generator.py の `_create_llm()` を修正
- `ChatOpenAI` の代わりに別の LLMClass を使用

## テスト

```bash
# 環境のテスト
uv run -c "from langchain_core.prompts import ChatPromptTemplate; print('OK')"

# 設定ファイルのテスト
uv run -c "from src.input.character_setting import load_setting_from_markdown; setting = load_setting_from_markdown('config/persona.md'); print(f'Days: {setting.days}')"
```

## ライセンス

MIT License

詳細は [LICENSE](LICENSE) を参照してください。

## サポート

- 問題がある場合は GitHub Issues で報告ください
- 新規参加者向けのドキュメント改善も大歓迎です
