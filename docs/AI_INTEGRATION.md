# AI Integration Guide (No Runtime API)

## Summary

This project runs without direct runtime model API calls.

AI-style enrichment is implemented as deterministic supplemental logic that populates `ai_*` audit fields and never overrides canonical parse decisions directly.

## Operating Model

1. Deterministic parse generates canonical hints.
2. Deterministic enrichment helper generates supplemental `ai_*` hints.
3. Reference evidence and scoring decide final action.
4. Low-confidence or ambiguous rows are manually reviewed.
5. Approved corrections are captured in `data/input/override.csv`.

## Why this model

- No runtime API access required.
- Fully deterministic and auditable.
- Compatible with SOP and decision rules.
- Safe for restricted environments.

## Recommended Workflow

### Run
```bash
python pipeline/cli.py --input data/input/input.csv --output data/output/parsed.csv
```

### Review
- Review rows where `action` is not `APPLY_CHANGE`.
- Use approved evidence sources.
- Promote validated corrections into overrides.

### Re-run
```bash
python pipeline/cli.py \
  --input data/input/input.csv \
  --output data/output/parsed.csv \
  --override-file data/input/override.csv
```

## `ai_*` field contract

- `ai_vendor_hint`: supplemental vendor candidate
- `ai_model_hint`: supplemental model candidate
- `ai_confidence`: helper confidence score
- `ai_reason`: deterministic reason code
- `ai_source`: helper source tag (for example `AGENT_VENDOR_MODEL`)

These fields are informational and must not bypass canonical decision gates.

## Determinism controls

- Fixed parsing and scoring logic
- No stochastic external model calls
- Stable rule files and override files
- Repeatable output given same inputs and sources

## Failure behavior

Fail closed:
- if enrichment helper has no valid suggestion, retain original canonical hints
- set `ai_reason` and `ai_source` to indicate no supplemental action

## Future optional extension

If runtime model access becomes available later, keep the same contract:
- model output remains supplemental
- deterministic validator must accept before use
- audit fields must capture acceptance/rejection reason
