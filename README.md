# NEW_EOL_Enrichment

A deterministic, auditable hardware normalisation pipeline.

This repository normalises raw hardware model strings into structured vendor, model, and version values with confidence scoring and full auditability.

## Quick Start

### 1. Deterministic Parse
```bash
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```

### 2. Deterministic Parse + Manual Review Queue
```bash
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```
Then review rows where `action != APPLY_CHANGE` and promote approved fixes into `data/input/override.csv`.

### 3. Deterministic Parse + Overrides
```bash
python pipeline/cli.py \
  --input data/input/input.csv \
  --output data/output/parsed.csv \
  --override-file data/input/override.csv
```

### 4. Full Command
```bash
python pipeline/cli.py \
  --input data/input/input.csv \
  --output data/output/parsed.csv \
  --reference-dir data/reference \
  --override-file data/input/override.csv
```

## Process Flow

```text
INPUT CSV
  |
  +--> Step 1: Deterministic Parse
  |      - detect_vendor()
  |      - extract_version()
  |      - strip_vendor_and_version()
  |
  +--> Step 2: Supplemental Deterministic Enrichment
  |      - generate ai_vendor_hint / ai_model_hint / ai_confidence
  |      - ai_* fields are advisory only
  |
  +--> Step 3: Reference Evidence Validation
  |      - fetch approved source_url
  |      - extract evidence_quote
  |      - apply bounded evidence boost
  |
  +--> Step 4: Decision Engine
  |      - confidence >= 0.80 -> APPLY_CHANGE
  |      - 0.50 to 0.79 -> SUGGEST_ONLY
  |      - < 0.50 -> NO_CHANGE
  |
  +--> Step 5: Reviewer Triage (pending rows only)
  |      - export rows with review_required=True
  |      - reviewer sets reviewer_decision_code and reviewer_comment
  |      - REVIEW_APPROVED_OVERRIDE requires non-empty reviewer_comment
  |
  +--> Step 6: Override Upsert + Re-run
     - apply approved decisions into data/input/override.csv
     - rerun parser for deterministic application
```

## Deterministic Enrichment Model

The project uses a deterministic enrichment helper for supplemental fields.

- No runtime API keys are required.
- `ai_*` fields are advisory metadata only.
- Canonical decisions remain rule-based and threshold-gated.

## Operator Steps

1. Run deterministic parse.

```bash
python -m pipeline.cli --input data/input/input.csv --output data/output/parsed.csv
```

2. Export pending review queue.

```bash
python -m pipeline.review_queue export-pending \
  --parsed-file data/output/parsed.csv \
  --output-file data/output/review_queue.csv
```

3. Reviewer updates `data/output/review_queue.csv`.
- Set `reviewer_decision_code`.
- Add `reviewer_comment` for all approved overrides.
- Optional: set `approved_vendor_hint`, `approved_model_hint`, `approved_version_hint` to override parser hints.

4. Apply reviewer decisions to override rules.

```bash
python -m pipeline.review_queue apply-decisions \
  --review-file data/output/review_queue.csv \
  --override-file data/input/override.csv
```

5. Re-run parser with overrides.

```bash
python -m pipeline.cli \
  --input data/input/input.csv \
  --output data/output/parsed.csv \
  --override-file data/input/override.csv
```

6. Optional validation pass before writing overrides.

```bash
python -m pipeline.review_queue apply-decisions \
  --review-file data/output/review_queue.csv \
  --override-file data/input/override.csv \
  --dry-run
```

### Review Queue Utility

Use the commands in **Operator Steps** for export and apply.
This section defines reviewer decisions and safeguards only.

Allowed reviewer decision codes:

- `REVIEW_APPROVED_OVERRIDE`
- `REVIEW_REJECTED_INSUFFICIENT_EVIDENCE`
- `REVIEW_REJECTED_RULE_CONFLICT`
- `REVIEW_UNKNOWN`

Safeguard:

- `REVIEW_APPROVED_OVERRIDE` fails apply-decisions when `reviewer_comment` is blank.

## Output Fields

- `input_raw`
- `vendor_hint`, `model_hint`, `version_hint`
- `confidence`, `action`, `reason_code`
- `source_url`, `evidence_quote`, `third_party_result`
- `ai_vendor_hint`, `ai_model_hint`, `ai_confidence`, `ai_reason`, `ai_source`
- `review_required`, `review_queue_status`, `review_recommendation`, `review_gate`, `review_decision_code`
- `output_value`

## Examples

### Example 1: Deterministic Parse
```bash
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```

### Example 2: Review Candidate Rows
```bash
python - <<'PY'
import csv
from pathlib import Path
p = Path('data/output/parsed.csv')
with p.open(newline='', encoding='utf-8') as fh:
    rows = list(csv.DictReader(fh))
for r in rows:
    if r.get('action') != 'APPLY_CHANGE':
        print(r.get('input_raw'), r.get('action'), r.get('confidence'))
PY
```

### Example 3: Apply Manual Overrides
```bash
python pipeline/cli.py \
  --input data/input/input.csv \
  --output data/output/parsed.csv \
  --override-file data/input/override.csv
```

## Environment Variables

No runtime model API variables are required for supported operation.

Optional local settings:

- `AI_CACHE_DIR` (if cache is used by deterministic enrichment helper)
- `AI_CACHE_ENABLED`

## Key Features

- Deterministic: same inputs and rules yield same outputs.
- Auditable: full trace via confidence, reason_code, evidence, and ai_* fields.
- No hallucination: UNKNOWN is used when evidence is insufficient.
- Review-first: low-confidence rows move to manual review.
- Override-driven improvement: approved corrections become reusable rules.

## Compliance

- `docs/SOP.md` - 5-step standard operating procedure
- `docs/decisions_rules.md` - confidence thresholds and decision rules
- `docs/project_idea.md` - original requirements

## Troubleshooting

### Missing optional enrichment module behavior
Pipeline continues using deterministic parse logic; inspect `ai_source` and `ai_reason`.

### How to run without any enrichment helper behavior
Run the CLI normally and rely on canonical fields and evidence-based scoring.

## Further Reading

- `docs/AI_INTEGRATION.md`
- `docs/AI_ARCHITECTURE.md`
- `AI_IMPLEMENTATION.md`
- `IMPLEMENTATION_CHECKLIST.md`
