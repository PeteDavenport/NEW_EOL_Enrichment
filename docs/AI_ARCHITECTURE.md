# AI Architecture (Deterministic + Review)

## Architecture overview

```text
Input row
  -> Deterministic parse (vendor/model/version)
  -> Deterministic enrichment helper (ai_* supplemental fields)
  -> Reference evidence validation
  -> Confidence scoring
  -> Decision engine (APPLY_CHANGE / SUGGEST_ONLY / NO_CHANGE)
  -> Output + audit trail
```

## Components

### 1. Canonical parser
- Produces `vendor_hint`, `model_hint`, `version_hint`.
- Primary source of truth for downstream decision logic.

### 2. Deterministic enrichment helper
- Produces `ai_vendor_hint`, `ai_model_hint`, `ai_confidence`, `ai_reason`, `ai_source`.
- Uses deterministic rules only.
- Never directly overrides canonical fields.

### 3. Evidence validator
- Fetches and validates approved reference sources.
- Extracts `evidence_quote` and updates confidence inputs.

### 4. Decision engine
- Applies thresholds from decision rules.
- Overwrite allowed only when confidence gate passes.

### 5. Human review loop
- Handles `SUGGEST_ONLY` and `NO_CHANGE` rows.
- Writes approved corrections to override file.

## Data flow contract

- Canonical fields: authoritative.
- `ai_*` fields: advisory and auditable.
- Overrides: highest-priority deterministic correction path.

## Determinism guarantees

Given same input, rules, references, and overrides:
- same canonical parse output
- same supplemental `ai_*` output
- same decision result

## Audit requirements

Each output row should retain:
- decision (`action`, `reason_code`)
- evidence (`source_url`, `evidence_quote`)
- supplemental metadata (`ai_*` fields)
- final application marker (`parse_applied`)

## Governance notes

- No direct runtime model API calls in current operating mode.
- Any future model integration must remain non-authoritative and pass deterministic validation gates.
