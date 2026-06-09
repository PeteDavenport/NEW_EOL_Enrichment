# NEW_EOL_Enrichment

**A deterministic, auditable hardware normalisation pipeline.**

This repository normalises raw hardware model strings into structured `vendor`, `model`, and `version` values with confidence scoring and full auditability.

---

## Quick Start

### 1. Deterministic-Only (No AI)
```bash
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```

### 2. With AI Enrichment (Requires OpenAI Key)
```bash
export OPENAI_API_KEY="sk-..."
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```

### 3. With Manual Overrides
```bash
python pipeline/cli.py \
  --input data/input/input.csv \
  --output data/output/parsed.csv \
  --override-file data/input/override.csv
```

### 4. With Custom Reference Directory
```bash
python pipeline/cli.py \
  --input data/input/input.csv \
  --output data/output/parsed.csv \
  --reference-dir data/reference
```

### 5. Full Command (All Options)
```bash
export OPENAI_API_KEY="sk-..."
python pipeline/cli.py \
  --input data/input/input.csv \
  --output data/output/parsed.csv \
  --reference-dir data/reference \
  --override-file data/input/override.csv
```

---

## Process Overview

```
Raw Input String
        ↓
[1] Deterministic Parse
    - detect_vendor()
    - extract_version()
    - strip_vendor_and_version()
        ↓
[2] AI Enrichment (Optional)
    - LLM call (if OPENAI_API_KEY set)
    - Cache & fallback to deterministic
        ↓
[3] Reference Validation
    - Fetch external source URL
    - Extract evidence quote
    - Boost confidence if match found
        ↓
[4] Score & Decide
    - Calculate final confidence
    - If confidence >= 0.80 → APPLY_CHANGE
    - Otherwise → preserve original
        ↓
Structured Output (vendor, model, version, confidence, reason_code, ai_*, etc.)
```

---

## File Reference

### Configuration & Execution
| File | Purpose |
|------|---------|
| `pipeline/cli.py` | Command-line entry point; handles arguments and orchestrates pipeline |
| `pipeline/parse.py` | Core parsing logic; vendor/model/version detection + scoring |
| `pipeline/ai_vendor_enricher.py` | **NEW:** LLM integration with caching & fallback |
| `.env.example` | **NEW:** Environment variable template (copy to `.env`) |

### Data
| Directory | Purpose |
|-----------|---------|
| `data/input/input.csv` | Raw hardware strings to parse |
| `data/input/override.csv` | Manual overrides (optional; matched before parsing) |
| `data/reference/hardware_reference_rules.csv` | External sources: manufacturer URLs for validation |
| `data/output/parsed.csv` | Output: parsed vendor/model/version + confidence scores |

### Documentation
| File | Purpose |
|------|---------|
| `docs/SOP.md` | Standard Operating Procedure (5-step process) |
| `docs/decisions_rules.md` | Confidence thresholds & decision rules |
| `docs/project_idea.md` | Original project requirements |
| `docs/AI_INTEGRATION.md` | **NEW:** AI setup guide & troubleshooting |
| `docs/AI_ARCHITECTURE.md` | **NEW:** Technical architecture & audit trail |
| `AI_IMPLEMENTATION.md` | **NEW:** Summary of AI integration |
| `IMPLEMENTATION_CHECKLIST.md` | **NEW:** Deployment verification |

### Tests
| File | Purpose |
|------|---------|
| `tests/test_ai_enrichment.py` | **NEW:** AI enrichment test suite |

---

## How It Works: Step by Step

### Step 1: Parse Input
- Clean and tokenize raw string
- Detect vendor (match against known aliases)
- Extract version (regex patterns)
- Strip vendor/version from remainder → model hint

### Step 2: AI Enrichment (Optional)
- If `OPENAI_API_KEY` set: Call GPT-4-turbo with structured prompt
- Check cache first (fast, deterministic)
- Fall back to deterministic logic if LLM unavailable
- Record `ai_vendor_hint`, `ai_model_hint`, `ai_confidence`, `ai_reason`, `ai_source` for audit

### Step 3: Reference Validation
- Look up manufacturer in `data/reference/hardware_reference_rules.csv`
- Fetch external source URL (webpage)
- Search for model string on page
- Extract evidence quote if match found
- Boost confidence if evidence quality high

### Step 4: Score & Decide
- Combine vendor/model/version confidence scores
- Apply evidence boost if applicable
- Calculate final confidence (0.0–1.0)
- If confidence >= 0.80 → APPLY_CHANGE (overwrite original)
- Otherwise → NO_CHANGE (preserve original)

### Step 5: Output Results
- CSV with all audit fields:
  - `input_raw`: original string
  - `vendor_hint`, `model_hint`, `version_hint`: parsed values
  - `confidence`: final confidence score (0.0–1.0)
  - `reason_code`: why decision was made (CONFIDENCE_HIGH, CONFIDENCE_LOW, etc.)
  - `source_url`: where evidence came from (if any)
  - `evidence_quote`: snippet from source page (if any)
  - `ai_vendor_hint`, `ai_model_hint`, `ai_confidence`, `ai_reason`, `ai_source`: AI audit fields
  - `output_value`: final normalized value (or original if not applied)

---

## Examples

### Example 1: Simple Parse (No References, No AI)
```bash
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```

Input: `"Dell PowerEdge R750 Gen13"`  
Output:
```csv
input_raw,vendor_hint,model_hint,version_hint,confidence,reason_code,source_url,evidence_quote,output_value
"Dell PowerEdge R750 Gen13","Dell","R750","Gen13","0.95","CONFIDENCE_HIGH","LOCAL_RULESET","","R750"
```

### Example 2: With AI Enrichment
```bash
export OPENAI_API_KEY="sk-..."
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```

Same input; additional AI audit fields:
```csv
ai_vendor_hint,ai_model_hint,ai_confidence,ai_reason,ai_source
"Dell","R750","0.95","PARSE_SUCCESS","LLM_OPENAI"
```

(Second run uses cache, shows `ai_source: CACHE`)

### Example 3: With Manual Override
```bash
python pipeline/cli.py \
  --input data/input/input.csv \
  --output data/output/parsed.csv \
  --override-file data/input/override.csv
```

If `override.csv` contains:
```csv
input_raw,vendor_hint,model_hint,version_hint,comment
"Dell PowerEdge R750 Gen13","Dell","PowerEdge R750","Gen13","Manual correction"
```

Output will use override values with `source_url: OVERRIDE_RULESET` and `confidence: 1.00`.

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | (none) | OpenAI API key; if set, enables AI enrichment |
| `OPENAI_MODEL` | `gpt-4-turbo` | Which GPT model to use |
| `AI_CACHE_DIR` | `.cache/ai_vendor_enricher` | Where to store LLM result cache |
| `AI_CACHE_ENABLED` | `true` | Enable/disable result caching |
| `AI_PROVIDER` | `openai` | LLM provider (currently: openai) |

### Setup Example
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
export OPENAI_API_KEY="sk-..."
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```

---

## Key Features

✅ **Deterministic**: Same inputs always produce same outputs (cache + fixed temperature)  
✅ **Auditable**: Full audit trail in every record (confidence, reason_code, ai_* fields)  
✅ **No Hallucination**: Uses only approved sources; returns UNKNOWN when unsure  
✅ **AI-Optional**: Works without OpenAI key (deterministic fallback)  
✅ **Cached**: Results cached by input hash; fast repeat processing  
✅ **Reference-Aware**: Validates against external manufacturer sources  
✅ **Overridable**: Manual corrections via CSV file  
✅ **Backward-Compatible**: Existing logic unchanged; AI is supplemental  

---

## Compliance

- ✅ [docs/SOP.md](docs/SOP.md) — 5-step standard operating procedure
- ✅ [docs/decisions_rules.md](docs/decisions_rules.md) — Confidence thresholds (>= 0.80 to apply)
- ✅ [docs/project_idea.md](docs/project_idea.md) — Original requirements

---

## Troubleshooting

### LLM Timeout or Connection Error
The pipeline falls back to deterministic parsing automatically. Check `ai_source` field in output to confirm.

### "ModuleNotFoundError: No module named 'openai'"
Install: `pip install openai>=1.0.0`  
Or run in deterministic-only mode (don't set `OPENAI_API_KEY`).

### Cache Corruption
Delete `.cache/ai_vendor_enricher/` and re-run. Results will be recomputed and cached.

### How to Run Deterministically (No AI)
Don't set `OPENAI_API_KEY`:
```bash
unset OPENAI_API_KEY
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```

Output will show `ai_source: DETERMINISTIC_FALLBACK` for all records.

---

## Further Reading

- **Getting Started**: [docs/AI_INTEGRATION.md](docs/AI_INTEGRATION.md)
- **Architecture**: [docs/AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md)
- **Implementation Details**: [AI_IMPLEMENTATION.md](AI_IMPLEMENTATION.md)
- **Deployment Checklist**: [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md)
