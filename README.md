生成AIを用いて、1週間分の日記を生成する

# 日記内容
- コロナ禍で外出自粛が続く中、2日目に通信障害がおこる
- 新卒のエンジニア（開発未経験）
- 4/1~4/7
- 一日あたりおおむね400文字（目安350〜450字）

# 設定方法
- ペルソナ設定は `persona.md` を編集して変更する
- `persona.md` は通常のMarkdown見出しで記述できる
  - `## 主人公`
  - `## 状況`
  - `## 期間` (開始日と日数)
  - `## イベント` (0件以上)
- イベントは複数行で記述可能
  - `2日目に発生` のような行を起点に1イベントとして認識
  - 続く行はそのイベントの説明として連結
  - イベント見出し自体を省略した場合は「イベントなし」として扱う


# プロンプト編集
- プロンプトは `prompts.md` で編集できる
- `# System Prompt` はモデルへの共通指示
- `# User Prompt Template` は日記生成条件テンプレート
- User Template では以下の変数を使用できる
  - `{dates}`
  - `{role}`
  - `{background}`
  - `{incidents_text}`

# エラー時の挙動
- 設定ファイル読込や OpenRouter 生成に失敗した場合は、フォールバック生成せずエラーのみ表示して終了する
- OpenRouterの429レート制限時は、`AI_JOURNAL_MAX_RETRIES` 回だけ再試行し、`OPENROUTER_FALLBACK_MODELS` が設定されていれば順にフォールバックする

# OpenRouter設定（.env）
- `OPENROUTER_API_KEY`: OpenRouterのAPIキー
- `OPENROUTER_MODEL`: 第一候補のモデル名。無料枠を使う場合は `:free` 付きのモデルを設定する
- `OPENROUTER_FALLBACK_MODELS`: 代替モデルをカンマ区切りで指定（任意）。こちらも無料モデルを並べる
- `AI_JOURNAL_MAX_RETRIES`: 429発生時の再試行回数。無料枠では 2〜3 程度が目安
- `AI_JOURNAL_MAX_OUTPUT_TOKENS`: 生成時の最大出力トークン

無料枠の初期設定例:

- `OPENROUTER_MODEL="qwen/qwen3.6-plus-preview:free"`
- `OPENROUTER_FALLBACK_MODELS="openai/gpt-oss-120b:free"`

# ファイル構成
- `character_setting.py`: キャラクター設定の読み込みとパース
- `prompt_templates.py`: `prompts.md` から見出し単位でプロンプト読込
- `prompt_builder.py`: プロンプト生成
- `journal_generator.py`: OpenRouter呼び出し
- `main.py`: 全体の実行フロー
- `prompts.md`: 編集可能なSystem/Userプロンプト

# スタック
- Python
- LangChain（PromptTemplate + LLM + OutputParser のチェーン構成）
- OpenRouter API（OpenAI互換エンドポイント）
