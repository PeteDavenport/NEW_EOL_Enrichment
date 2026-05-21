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

The parser may use page evidence to improve inferred vendor/model/version hints before computing the final confidence.

## Key Requirement
- No hallucination
- No uncontrolled overwrites
- Fully auditable process