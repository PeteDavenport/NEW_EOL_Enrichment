# Project Idea — Hardware Model Normalisation

## Problem
Input CSV contains inconsistent hardware identifiers:
- Sometimes vendor + model
- Sometimes vendor + version
- Sometimes model only
- Inconsistent casing, aliases, partial strings

This prevents downstream processes (e.g. lifecycle / EOSL enrichment).

## Objective
Create a repeatable pipeline that:
- Normalises to:
  - make
  - model
  - version
- Uses internet sources to improve accuracy
- Assigns a confidence score (0..1)
- Only applies changes when confidence is high

## Output
A structured dataset with:
- input_raw
- vendor_hint
- model_hint
- version_hint
- source_url
- evidence_quote
- third_party_result
- confidence
- action
- reason_code
- parse_applied
- output_value
- ai_vendor_hint
- ai_model_hint
- ai_confidence
- ai_reason
- ai_source

The parser may use page evidence to improve inferred vendor/model/version hints before computing the final confidence.
- The parser may also produce AI-derived vendor/model supplemental metadata in `ai_*` fields for audit and review.
The pipeline also supports manual override rules via `data/input/override.csv`, which can enforce vendor/model/version values with maximum confidence for specific raw inputs.

## Key Requirement
- No hallucination
- No uncontrolled overwrites
- Fully auditable process