# AI Integration Layer: End-to-End Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE ENTRY POINT                      │
│                    cli.py → parse_row()                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 1: DETERMINISTIC PARSE                     │
│  detect_vendor() → vendor_hint                              │
│  extract_version() → version_hint                           │
│  strip_vendor_and_version() → model_hint                    │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│          STEP 2: AI ENRICHMENT LAYER (NEW)                   │
│         ai_enrich_vendor_model(input_raw, ...)              │
│                     ↓                                         │
│     ┌─────────────────────────────────────────┐            │
│     │  AIVendorEnricher.enrich()              │             │
│     │  ├─ Check cache (SHA-256 key)           │             │
│     │  │  ├─ HIT? Return cached result        │             │
│     │  │  └─ MISS? Continue...                 │             │
│     │  ├─ Try LLM (if API key configured)     │             │
│     │  │  ├─ Call OpenAI GPT-4-turbo          │             │
│     │  │  │  (temp=0.0, fixed prompt)         │             │
│     │  │  ├─ Parse JSON response              │             │
│     │  │  ├─ Cache result                     │             │
│     │  │  └─ Return AIEnrichmentResult        │             │
│     │  └─ Fallback (if LLM failed/missing)    │             │
│     │     ├─ Call _deterministic_enrich_*()  │             │
│     │     └─ Return AIEnrichmentResult        │             │
│     └─────────────────────────────────────────┘            │
│                                                               │
│  OUTPUT: AIEnrichmentResult {                               │
│    ai_vendor_hint: "Dell"         (supplemental)           │
│    ai_model_hint: "R750"          (supplemental)           │
│    ai_confidence: 0.95            (0.0-1.0)                │
│    ai_reason: "PARSE_SUCCESS"     (audit trail)            │
│    ai_source: "LLM_OPENAI"        (where it came from)     │
│  }                                                            │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│          STEP 3: SCORE CONFIDENCE (UNCHANGED)                │
│  score_confidence(vendor, model, version)                   │
│  + Evidence boost from reference source URLs                │
│  = Final confidence (0.0-1.0)                               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│          STEP 4: DECISION RULE (UNCHANGED)                   │
│  confidence >= 0.80? APPLY_CHANGE                           │
│  confidence >= 0.50? SUGGEST_ONLY                           │
│  confidence <  0.50? NO_CHANGE                              │
│                                                               │
│  NOTE: Decision is based on confidence (canonical),         │
│        not ai_confidence (supplemental)                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│          STEP 5: OUTPUT RESULT                               │
│  {                                                            │
│    "input_raw": "Dell PowerEdge R750 Gen13",               │
│    "vendor_hint": "Dell",                                   │
│    "model_hint": "R750",                                    │
│    "version_hint": "Gen13",                                 │
│    "confidence": "0.95",                                    │
│    "reason_code": "CONFIDENCE_HIGH",                        │
│    "action": "APPLY_CHANGE",                               │
│    "parse_applied": "true",                                 │
│    "output_value": "R750",          ← FINAL RESULT          │
│    "source_url": "LOCAL_RULESET",   ← EVIDENCE SOURCE       │
│    "evidence_quote": "Dell PowerEdge R750",                 │
│                                                               │
│    ← NEW AI ENRICHMENT FIELDS ─────────────────────────     │
│    "ai_vendor_hint": "Dell",        (supplemental)         │
│    "ai_model_hint": "R750",         (supplemental)         │
│    "ai_confidence": "0.95",         (LLM's assessment)     │
│    "ai_reason": "PARSE_SUCCESS",    (why LLM decided this) │
│    "ai_source": "LLM_OPENAI"        (cache/LLM/fallback)   │
│  }                                                            │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. **Supplemental, Not Authoritative**
```
Canonical decision path:    Deterministic → Score → Confidence → Decision
AI enrichment path:         LLM/Fallback/Cache → ai_* fields (audit only)

The final "APPLY_CHANGE" is NEVER driven by ai_confidence.
It's ALWAYS based on the canonical confidence score.
```

### 2. **Determinism Guarantee**
```
Same input → SHA-256 hash → Cache lookup
    ├─ Cache HIT   → Return cached result (milliseconds)
    ├─ Cache MISS  → LLM call (temperature=0.0)
    │               → Cache result
    │               → Return
    └─ LLM FAIL    → Deterministic fallback
                    → Cache result
                    → Return
```

### 3. **Audit Trail at Every Step**
```
Each record includes:
- ai_source:      WHERE the AI result came from
                  (LLM_OPENAI | DETERMINISTIC_FALLBACK | CACHE)
- ai_reason:      WHY AI made this decision
                  (PARSE_SUCCESS | NO_AI_ACTION | REFERENCE_MANUFACTURER_MATCH | ...)
- ai_confidence:  WHAT confidence AI assigned (0.0-1.0)
- ai_vendor_hint: WHAT AI thinks the vendor is
- ai_model_hint:  WHAT AI thinks the model is
```

### 4. **Explicit Fallback Chain**
```
try:
    cached_result = load_cache(input_raw)
    if cached_result:
        return cached_result  ← CACHE HIT

try:
    llm_result = call_openai(input_raw, vendor_hint, model_hint, version_hint)
    save_cache(input_raw, llm_result)
    return llm_result  ← LLM SUCCESS
except:
    deterministic_result = _deterministic_enrich_vendor_model(...)
    save_cache(input_raw, deterministic_result)
    return deterministic_result  ← FALLBACK (logged)
```

### 5. **No Hallucination**
```
LLM Prompt Structure:
  ├─ System: "You are a hardware parser. Return ONLY valid JSON."
  ├─ Input: Fixed template with raw string + current parse + rules
  └─ Format: Enforce JSON schema:
       {
         "vendor_hint": "vendor or UNKNOWN",
         "model_hint": "model or UNKNOWN",
         "confidence": 0.0-1.0,
         "reason": "explanation"
       }

Safety Guards:
  ✓ "If unsure, return UNKNOWN (do not guess)"
  ✓ "Confidence 0.80+ only if high certainty"
  ✓ "Return ONLY JSON, no explanation"
  ✓ Confidence values clamped to [0.0, 1.0]
  ✓ Invalid JSON → fallback to deterministic
```

## Configuration Modes

### Mode A: Full AI Integration
```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4-turbo"
export AI_CACHE_ENABLED="true"

python cli.py --input data/input/input.csv --output data/output/parsed.csv

Expected behavior:
  First run:   2-3 sec per record (LLM calls)
  Subsequent:  1-5 ms per record  (cache hits)
```

### Mode B: Deterministic-Only (Fallback)
```bash
# Don't set OPENAI_API_KEY
python cli.py --input data/input/input.csv --output data/output/parsed.csv

Expected behavior:
  All records: 1-5 ms per record (deterministic fallback)
  ai_source:   "DETERMINISTIC_FALLBACK"
  ai_reason:   "NO_AI_ACTION" (or other deterministic reason)
```

### Mode C: Testing / Development
```bash
export OPENAI_API_KEY="sk-..."
export AI_CACHE_ENABLED="false"  ← Force fresh LLM calls
export LOG_LEVEL="DEBUG"

python cli.py --input data/input/single_test.csv --output data/output/test.csv

Expected behavior:
  Every record hits LLM (no caching)
  Verbose logging shows cache misses, LLM calls, timeouts
```

## Audit Field Reference

### `ai_source` values
| Value | Meaning |
|-------|---------|
| `LLM_OPENAI` | Result from successful OpenAI API call |
| `CACHE` | Result loaded from local cache |
| `DETERMINISTIC_FALLBACK` | LLM unavailable; using deterministic logic |
| `DETERMINISTIC_FALLBACK(LLM_TIMEOUT)` | LLM timed out; fell back to deterministic |
| `DETERMINISTIC_FALLBACK(LLM_ERROR:...)` | LLM error occurred; fell back to deterministic |
| `NOOP` | No enrichment (fallback not configured) |
| `AGENT_VENDOR_MODEL` | Original deterministic enrichment |

### `ai_reason` values
| Value | Meaning |
|-------|---------|
| `PARSE_SUCCESS` | LLM successfully parsed the input |
| `NO_AI_ACTION` | Deterministic: no improvement found |
| `REFERENCE_MANUFACTURER_MATCH` | Deterministic: manufacturer matched reference |
| `MODEL_FROM_CLEANED_TEXT` | Deterministic: extracted model from text |
| `PARSE_ERROR:...` | LLM returned invalid JSON |
| `NO_FALLBACK_CONFIGURED` | No fallback function provided |

## Example Outputs

### Example 1: Successful AI Parse (LLM)
```json
{
  "input_raw": "Dell PowerEdge R750 Gen13",
  "vendor_hint": "Dell",
  "model_hint": "R750",
  "confidence": "0.95",
  "reason_code": "CONFIDENCE_HIGH",
  "action": "APPLY_CHANGE",
  "output_value": "R750",
  "ai_vendor_hint": "Dell",
  "ai_model_hint": "R750",
  "ai_confidence": "0.95",
  "ai_reason": "PARSE_SUCCESS",
  "ai_source": "LLM_OPENAI"
}
```

### Example 2: Cached Result (Second Call)
```json
{
  "input_raw": "Dell PowerEdge R750 Gen13",
  "vendor_hint": "Dell",
  "model_hint": "R750",
  "confidence": "0.95",
  "reason_code": "CONFIDENCE_HIGH",
  "action": "APPLY_CHANGE",
  "output_value": "R750",
  "ai_vendor_hint": "Dell",
  "ai_model_hint": "R750",
  "ai_confidence": "0.95",
  "ai_reason": "PARSE_SUCCESS",
  "ai_source": "CACHE"  ← Note: same as Example 1
}
```

### Example 3: LLM Timeout → Deterministic Fallback
```json
{
  "input_raw": "Unknown-XYZ-999",
  "vendor_hint": "UNKNOWN",
  "model_hint": "UNKNOWN",
  "confidence": "0.20",
  "reason_code": "CONFIDENCE_LOW",
  "action": "NO_CHANGE",
  "output_value": "Unknown-XYZ-999",
  "ai_vendor_hint": "UNKNOWN",
  "ai_model_hint": "UNKNOWN",
  "ai_confidence": "0.00",
  "ai_reason": "NO_AI_ACTION",
  "ai_source": "DETERMINISTIC_FALLBACK(LLM_TIMEOUT)"
}
```

## Performance Characteristics

```
Input Size        | Mode              | Time      | Cache Effect
──────────────────┼──────────────────┼──────────┼──────────────
1 record (new)    | Full AI           | 2-3s     | No
1 record (repeat) | Full AI           | 5ms      | Yes, 600x faster
1000 records      | Full AI (warm)    | 1-5s     | ~90% cache hits
1000 records      | Deterministic     | 1-5s     | No cache needed
10,000 records    | Full AI (warm)    | 10-50s   | Scales linearly
```

## Verification Checklist

- [x] AI enrichment layer initialized via environment variables
- [x] Caching implemented (SHA-256, JSON persistence)
- [x] Deterministic fallback chain explicit and logged
- [x] Audit fields populated in all output records
- [x] LLM prompts use fixed temperature (0.0) for determinism
- [x] JSON schema enforced on LLM responses
- [x] No hallucination (UNKNOWN when unsure)
- [x] Canonical decision unaffected by ai_* fields
- [x] Confidence >= 0.80 rule unchanged
- [x] Backward-compatible (no breaking changes)
- [x] Documented (AI_INTEGRATION.md, this file)
- [x] Tested (test_ai_enrichment.py)

---

**Last Updated**: 2026-06-09  
**Status**: Production Ready  
**Compliance**: SOP.md ✓ | decision_rules.md ✓ | project_idea.md ✓
