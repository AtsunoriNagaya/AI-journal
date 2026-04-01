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
- 旧形式の `key: value` も後方互換で読み込み可能

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
- 設定ファイル読込や Gemini 生成に失敗した場合は、フォールバック生成せずエラーのみ表示して終了する

# ファイル構成
- `character_setting.py`: キャラクター設定の読み込みとパース
- `prompt_templates.py`: `prompts.md` から見出し単位でプロンプト読込
- `prompt_builder.py`: プロンプト生成
- `journal_generator.py`: Gemini呼び出し
- `main.py`: 全体の実行フロー
- `prompts.md`: 編集可能なSystem/Userプロンプト

# スタック
- Python
- LangChain（PromptTemplate + LLM + OutputParser のチェーン構成）
- Gemini API(gemini 2.5-flash)
