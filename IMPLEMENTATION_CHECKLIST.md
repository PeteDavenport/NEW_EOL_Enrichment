# Implementation Checklist (No Runtime API)

## Core parser

- [x] Deterministic vendor/model/version parsing
- [x] Confidence scoring and threshold decisions
- [x] Reference evidence extraction and scoring input
- [x] Override rule support with top priority

## Supplemental enrichment

- [x] Deterministic enrichment helper for vendor/model supplement
- [x] `ai_vendor_hint` output
- [x] `ai_model_hint` output
- [x] `ai_confidence` output
- [x] `ai_reason` output
- [x] `ai_source` output
- [x] Non-authoritative behavior enforced

## Review workflow

- [x] `SUGGEST_ONLY` / `NO_CHANGE` rows available for review
- [x] Manual correction path via `data/input/override.csv`
- [x] Deterministic re-run with approved overrides

## Documentation

- [x] README updated to deterministic + review model
- [x] AI integration guide updated (no runtime API)
- [x] AI architecture updated (deterministic + review)
- [x] SOP/decision rules/project idea aligned with supplemental AI metadata

## Validation

- [x] No runtime API key required for supported operation
- [x] Output remains auditable and repeatable
- [x] Canonical decision logic remains authoritative
