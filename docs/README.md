# AI Journal

逕滓・AI・・penRouter API・峨ｒ菴ｿ逕ｨ縺励※縲・騾ｱ髢薙・荳雋ｫ諤ｧ縺ｮ縺ゅｋ譌･險倥ｒ閾ｪ蜍慕函謌舌☆繧九ヤ繝ｼ繝ｫ縲よ律蛻･繝ｫ繝ｼ繝励→繝√Ε繝・ヨ螻･豁ｴ繧呈ｴｻ逕ｨ縺励∝推譌･縺ｮ蜀・ｮｹ縺檎泝逶ｾ縺励↑縺・ｈ縺・↓縺励※縺・∪縺吶・

## 繧ｯ繧､繝・け繧ｹ繧ｿ繝ｼ繝・

### 蠢・ｦ√↑迺ｰ蠅・
- Python 3.11+
- uv・医ヱ繝・こ繝ｼ繧ｸ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ・・

### 繧ｻ繝・ヨ繧｢繝・・

```bash
# 迺ｰ蠅・､画焚縺ｮ險ｭ螳・
cp .env.example .env
# .env 縺ｫOpenRouter API 繧ｭ繝ｼ繧定ｨ伜・

# 萓晏ｭ倬未菫ゅ・繧､繝ｳ繧ｹ繝医・繝ｫ
uv sync

# 繝壹Ν繧ｽ繝願ｨｭ螳壹ｒ邱ｨ髮・
# persona.md 繧堤ｷｨ髮・＠縺ｦ縲∫函謌仙ｯｾ雎｡縺ｮ莠ｺ迚ｩ繝ｻ譛滄俣繝ｻ繧､繝吶Φ繝域ュ蝣ｱ繧定ｨ伜・

# 螳溯｡・
uv run main.py
```

### 蜃ｺ蜉・
stdout 縺ｫ譌･莉倩ｦ句・縺嶺ｻ倥″縺ｮ譌･險倥′1譌･縺壹▽繝ｪ繧｢繝ｫ繧ｿ繧､繝縺ｧ蜃ｺ蜉帙＆繧後∪縺呻ｼ・

```
04/01
<1譌･逶ｮ縺ｮ譌･險假ｼ育ｴ・80縲・20蟄暦ｼ・

04/02
<2譌･逶ｮ縺ｮ譌･險假ｼ育ｴ・80縲・20蟄暦ｼ・

...
```

## 險ｭ螳壽婿豕・

### 繝壹Ν繧ｽ繝願ｨｭ螳夲ｼ・ersona.md・・

```markdown
## 荳ｻ莠ｺ蜈ｬ
譁ｰ蜊偵・繧ｨ繝ｳ繧ｸ繝九い・磯幕逋ｺ譛ｪ邨碁ｨ難ｼ・

## 迥ｶ豕・
繧ｳ繝ｭ繝顔ｦ阪〒螟門・閾ｪ邊帙′邯壹￥

## 譛滄俣
髢句ｧ区律 2026-04-01
7譌･髢・

## 繧､繝吶Φ繝・
2譌･逶ｮ縺ｫ逋ｺ逕・
騾壻ｿ｡髫懷ｮｳ

7譌･縺ｾ縺ｧ螳悟・縺ｫ縺ｪ縺翫ｉ縺壹√▽縺ｪ縺後ｋ縺ｨ縺阪→縺､縺ｪ縺後ｉ縺ｪ縺・→縺阪′縺ゅｋ・井ｸ榊ｮ牙ｮ夲ｼ・
```

### 繝励Ο繝ｳ繝励ヨ險ｭ螳夲ｼ・rompts.md・・

- `# System Prompt`: LLM 縺ｸ縺ｮ蜈ｱ騾壽欠遉ｺ・育ｳｻ邨ｱ逧・↑謖・､ｺ・・
- `# Common Guidelines`: 蜈ｨ譌･蜈ｱ騾壹・繧ｬ繧､繝峨Λ繧､繝ｳ
- `# Daily User Prompt Template`: 譌･蛻･繝励Ο繝ｳ繝励ヨ繝・Φ繝励Ξ繝ｼ繝・
  - 菴ｿ逕ｨ蜿ｯ閭ｽ縺ｪ螟画焚: `{date}`, `{day_number}`, `{total_days}`, `{role}`, `{background}`, `{incident_text}`

### 迺ｰ蠅・､画焚險ｭ螳夲ｼ・env・・

```env
# 蠢・・
OPENROUTER_API_KEY=your-api-key-here

# 逕ｨ諢乗耳螂ｨ
OPENROUTER_MODEL=qwen/qwen3.6-plus-preview:free
OPENROUTER_FALLBACK_MODELS=openai/gpt-oss-120b:free

# 繧ｪ繝励す繝ｧ繝ｳ・医ョ繝輔か繝ｫ繝亥､縺ゅｊ・・
AI_JOURNAL_MAX_RETRIES=1
AI_JOURNAL_MAX_OUTPUT_TOKENS=1500
OPENROUTER_SITE_URL=https://example.com
OPENROUTER_SITE_NAME=MyApp
```

## 繝輔ぃ繧､繝ｫ讒区・

| 繝輔ぃ繧､繝ｫ | 雋ｬ蜍・|
|---------|------|
| **main.py** | 繧ｨ繝ｳ繝医Μ繝ｼ繝昴う繝ｳ繝医・蜈ｨ菴薙ヵ繝ｭ繝ｼ蛻ｶ蠕｡ |
| **character_setting.py** | persona.md 縺ｮ隱ｭ縺ｿ霎ｼ縺ｿ縺ｨ讀懆ｨｼ |
| **prompt_templates.py** | prompts.md 縺ｮ繝・Φ繝励Ξ繝ｼ繝郁ｪｭ縺ｿ霎ｼ縺ｿ |
| **prompt_builder.py** | 譌･蛻･繝励Ο繝ｳ繝励ヨ縺ｮ逕滓・ |
| **journal_generator.py** | OpenRouter API 蜻ｼ縺ｳ蜃ｺ縺励・繝｡繝｢繝ｪ邂｡逅・|
| **persona.md** | 繝壹Ν繧ｽ繝翫・譛滄俣繝ｻ繧､繝吶Φ繝医・螳夂ｾｩ |
| **prompts.md** | System繝ｻ蜈ｱ騾壹・譌･蛻･繝励Ο繝ｳ繝励ヨ繝・Φ繝励Ξ繝ｼ繝・|
| **ARCHITECTURE.md** | 隧ｳ邏ｰ縺ｪ雋ｬ蜍吶→諡｡蠑ｵ繧ｬ繧､繝・|

## 繧｢繝ｼ繧ｭ繝・け繝√Ε

雋ｬ蜍吶＃縺ｨ縺ｫ螻､繧貞・髮｢縺励※縺・∪縺吶りｩｳ邏ｰ縺ｯ [ARCHITECTURE.md](ARCHITECTURE.md) 繧貞盾辣ｧ縺上□縺輔＞縲・

```
蜈･蜉帛ｱ､ (character_setting)
   竊・
繝・Φ繝励Ξ繝ｼ繝亥ｱ､ (prompt_templates)
   竊・
繝励Ο繝ｳ繝励ヨ逕滓・螻､ (prompt_builder)
   竊・
逕滓・螻､ (journal_generator) 竊・繝｡繝｢繝ｪ繝吶・繧ｹ縺ｮ譌･蛻･繝ｫ繝ｼ繝・
   竊・
蛻ｶ蠕｡螻､ (main) 竊・繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ
   竊・
stdout 竊・譌･險俶悽譁・
```

## 繝医Λ繝悶Ν繧ｷ繝･繝ｼ繝・ぅ繝ｳ繧ｰ

### API 繧ｭ繝ｼ繧ｨ繝ｩ繝ｼ
```
[ERROR] 險ｭ螳壹ヵ繧｡繧､繝ｫ縺ｮ隱ｭ縺ｿ霎ｼ縺ｿ縺ｫ螟ｱ謨励＠縺ｾ縺励◆: OPENROUTER_API_KEY is not set
```
竊・.env 縺ｫ `OPENROUTER_API_KEY` 繧定ｿｽ蜉縺励※縺上□縺輔＞

### 繝｢繝・Ν蛻ｩ逕ｨ荳榊庄繧ｨ繝ｩ繝ｼ
```
[ERROR] 譌･險倥・逕滓・縺ｫ螟ｱ謨励＠縺ｾ縺励◆: OpenRouter 縺ｮ繝ｬ繝ｼ繝亥宛髯舌∪縺溘・繝｢繝・Ν譛ｪ謠蝉ｾ・..
```
竊・蛻･縺ｮ繝｢繝・Ν繧定ｩｦ縺吶°縲～AI_JOURNAL_MAX_RETRIES` 繧貞｢励ｄ縺励※縺上□縺輔＞

### 譌･險倥′遏ｭ縺吶℃繧・
竊・prompts.md 縺ｮ `# Daily User Prompt Template` 縺ｧ縲後♀縺翫・縺ｭ400蟄励阪ｒ縲後♀縺翫・縺ｭ450蟄励阪↓螟画峩縺吶ｋ縺九～AI_JOURNAL_MAX_OUTPUT_TOKENS` 繧剃ｸ翫￡縺ｦ縺上□縺輔＞

## 諡｡蠑ｵ髢狗匱繧ｬ繧､繝・

譁ｰ縺励＞讖溯・繧定ｿｽ蜉縺吶ｋ蜑阪↓縲ーARCHITECTURE.md](ARCHITECTURE.md) 縺ｮ縲梧僑蠑ｵ繝昴う繝ｳ繝医阪そ繧ｯ繧ｷ繝ｧ繝ｳ繧堤｢ｺ隱阪￥縺縺輔＞縲・

### 繧医￥縺ゅｋ諡｡蠑ｵ萓・

**譁ｰ縺励＞蜈･蜉帛ｽ｢蠑擾ｼ・AML 縺ｪ縺ｩ・峨ｒ霑ｽ蜉**
- character_setting.py 縺ｫ譁ｰ繝代・繧ｵ繝ｼ繧定ｿｽ蜉
- 蜃ｺ蜉帙・ `JournalSetting` 縺ｫ邨ｱ荳

**繝・ヰ繝・げ蜃ｺ蜉帙ｒ霑ｽ蜉**
- main.py 縺ｫ `--debug` 繝輔Λ繧ｰ繧定ｿｽ蜉縺励∽ｸｭ髢薙・繝ｭ繝ｳ繝励ヨ繧定｡ｨ遉ｺ

**繝ｭ繝ｼ繧ｫ繝ｫ繝｢繝・Ν・・llama 縺ｪ縺ｩ・峨↓蛻・ｊ譖ｿ縺・*
- journal_generator.py 縺ｮ `_create_llm()` 繧剃ｿｮ豁｣
- `ChatOpenAI` 縺ｮ莉｣繧上ｊ縺ｫ蛻･縺ｮ LLMClass 繧剃ｽｿ逕ｨ

## 繝・せ繝・

```bash
# 迺ｰ蠅・・繝・せ繝・
uv run -c "from langchain_core.prompts import ChatPromptTemplate; print('OK')"

# 險ｭ螳壹ヵ繧｡繧､繝ｫ縺ｮ繝・せ繝・
uv run -c "from character_setting import load_setting_from_markdown; setting = load_setting_from_markdown(); print(f'Days: {setting.days}')"
```

## 繝ｩ繧､繧ｻ繝ｳ繧ｹ

・医・繝ｭ繧ｸ繧ｧ繧ｯ繝井ｾ晏ｭ假ｼ・

## 繧ｵ繝昴・繝・

- 蝠城｡後′縺ゅｋ蝣ｴ蜷医・ GitHub Issues 縺ｧ蝣ｱ蜻翫￥縺縺輔＞
- 譁ｰ隕丞盾蜉閠・髄縺代・繝峨く繝･繝｡繝ｳ繝域隼蝟・ｂ螟ｧ豁楢ｿ弱〒縺・
