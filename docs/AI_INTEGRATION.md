# AI Vendor Enricher Integration Guide

## Overview

The hardware normalisation pipeline now includes a real AI integration layer that enriches vendor/model detection using LLMs (Language Models) while maintaining full backward compatibility with deterministic fallback and comprehensive audit controls.

## Architecture

```
ai_enrich_vendor_model()
    ↓
AIVendorEnricher (with caching & fallback)
    ├→ LLM API (if configured)
    │   ├ OpenAI GPT-4 (temperature=0.0 for determinism)
    │   ├ Cached results for determinism
    │   └ Structured JSON prompts to minimize hallucination
    └→ Deterministic fallback
        └ Original vendor-matching + text-cleaning logic
```

## Setup

### 1. Install Dependencies

```bash
pip install openai>=1.0.0
```

### 2. Environment Variables

Configure the AI layer via environment variables:

```bash
# OpenAI API key (required for AI mode; optional for deterministic-only mode)
export OPENAI_API_KEY="sk-..."

# Model to use (default: gpt-4-turbo)
export OPENAI_MODEL="gpt-4-turbo"

# LLM provider (default: openai)
export AI_PROVIDER="openai"

# Cache directory (default: .cache/ai_vendor_enricher)
export AI_CACHE_DIR=".cache/ai_vendor_enricher"

# Enable/disable result caching (default: true)
export AI_CACHE_ENABLED="true"
```

### 3. Running the Pipeline

```bash
# With AI (requires OPENAI_API_KEY)
python cli.py --input data/input/input.csv --output data/output/parsed.csv

# Deterministic-only (no API key needed)
python cli.py --input data/input/input.csv --output data/output/parsed.csv
```

## Audit Controls

All AI enrichment decisions are recorded in the output CSV with these supplemental fields:

| Field | Type | Purpose |
|-------|------|---------|
| `ai_vendor_hint` | string | AI's vendor guess (supplemental) |
| `ai_model_hint` | string | AI's model guess (supplemental) |
| `ai_confidence` | float [0.0–1.0] | AI's confidence in its parse |
| `ai_reason` | string | Why AI made this decision (e.g., `PARSE_SUCCESS`, `REFERENCE_MANUFACTURER_MATCH`, `NO_AI_ACTION`) |
| `ai_source` | string | Source of the result (e.g., `LLM_OPENAI`, `DETERMINISTIC_FALLBACK`, `CACHE`) |

## Decision Flow

```
Input → Deterministic Parse → AI Enrichment (cache/LLM/fallback)
    ↓                          ↓
    │                          └→ ai_* audit fields
    │
    └→ Evidence Fetch → Final Confidence Calc
        ↓
        Decision (confidence >= 0.80 → APPLY_CHANGE)
        ↓
        Output (preserves input if confidence < 0.80)
```

**Key point:** AI enrichment is *supplemental*. The final decision to overwrite is based on `confidence` (not `ai_confidence`), which combines:
- Deterministic vendor/model/version match scores
- External reference validation
- Evidence gathering from URLs

## Determinism Guarantees

Given the same inputs, the pipeline produces identical results:

1. **Caching**: Results are cached by SHA-256 hash of the input string
2. **Fixed Temperature**: LLM calls use `temperature=0.0` (no randomness)
3. **Consistent Prompts**: Structured JSON-based prompts
4. **Explicit Fallback**: Deterministic chain clearly defined

## Audit Examples

### Example 1: AI Successfully Enriches

```
input_raw: "Dell R750 Gen13"
vendor_hint: "Dell"
model_hint: "R750"
version_hint: "Gen13"
ai_vendor_hint: "Dell"      ← Same as input
ai_model_hint: "R750"       ← Same as input
ai_confidence: 0.95         ← High confidence
ai_reason: "PARSE_SUCCESS"
ai_source: "LLM_OPENAI"
confidence: 0.95            ← Final confidence (used for decision)
action: "APPLY_CHANGE"      ← Overwrite original
```

### Example 2: AI Falls Back to Deterministic

```
input_raw: "Unknown-XYZ-123"
vendor_hint: "UNKNOWN"
model_hint: "UNKNOWN"
version_hint: "123"
ai_vendor_hint: "UNKNOWN"   ← Fallback couldn't improve
ai_model_hint: "UNKNOWN"
ai_confidence: 0.0
ai_reason: "NO_AI_ACTION"
ai_source: "DETERMINISTIC_FALLBACK(LLM_ERROR:timeout)"
confidence: 0.20            ← Low confidence
action: "NO_CHANGE"         ← Preserve original
output_value: "Unknown-XYZ-123"
```

### Example 3: Cache Hit

```
input_raw: "Cisco Nexus 7010"  (seen before)
ai_vendor_hint: "Cisco"
ai_model_hint: "Nexus 7010"
ai_confidence: 0.88
ai_reason: "PARSE_SUCCESS"
ai_source: "CACHE"              ← Fast result, no LLM call
```

## Failure Modes & Recovery

| Scenario | Behavior | Recovery |
|----------|----------|----------|
| No API key | Use deterministic-only | Graceful; set `ai_source: "DETERMINISTIC_FALLBACK"` |
| LLM timeout | Fall back to deterministic | Logged; cache not updated |
| Invalid JSON from LLM | Parse error → fallback | Logged; uses deterministic instead |
| Cache corrupted | Ignore cache, recompute | Logged; automatically refreshes |

## Performance

- **Cache Hit**: ~0.5ms per record (in-memory + disk)
- **LLM Call**: ~1-3s per record (network latency)
- **Deterministic Fallback**: ~1-5ms per record

For large datasets, enable caching and consider batching LLM calls.

## Testing Determinism

```python
from pipeline.parse import parse_row, load_reference_rules, load_override_rules

# First run
rules = load_reference_rules(Path("data/reference"))
result1 = parse_row("Dell R750 Gen13", rules)

# Second run (same input)
result2 = parse_row("Dell R750 Gen13", rules)

# Verify identical results
assert result1 == result2
assert result1["ai_source"] in ("LLM_OPENAI", "CACHE")  # Not different on 2nd call
```

## Disabling AI (Fallback Only)

To run in fully deterministic mode (no LLM calls):

```bash
# Don't set OPENAI_API_KEY
python cli.py --input data/input/input.csv --output data/output/parsed.csv
```

The pipeline will:
1. Skip AI enrichment initialization
2. Use deterministic fallback for all records
3. Complete in seconds instead of minutes

## Contributing / Extending

To add another LLM provider:

1. Create `AIVendorEnricher._call_llm_anthropic()` method
2. Update `_init_ai_enricher()` to handle provider dispatch
3. Ensure same input → same output contract for determinism

Example: [ai_vendor_enricher.py](ai_vendor_enricher.py#L100)
