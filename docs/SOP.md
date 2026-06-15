# SOP — Hardware Normalisation Pipeline

## 1. Purpose
Convert inconsistent hardware model strings into structured:
- make
- model
- version
with confidence scoring and auditability.

## 2. Actors
- System: Python pipeline
- Operator: runs the process

## 3. Inputs
- CSV file with raw hardware strings
- Manufacturer-level external reference directory containing source URLs (`.csv` or `.json`)

## 4. Outputs
- CSV with:
  - make, model, version
  - confidence
  - reason_code
  - source_url
  - evidence_quote
  - reference rule source when matched

## 5. Step-by-step Process

### Step 1 — Parse Input
- Clean string
- Tokenise
- Identify candidate vendor/model/version hints
- Enrich vendor/model candidates with a deterministic AI-style agent and record supplemental `ai_*` metadata
- If a manufacturer reference exists, fetch its `source_url` and search for the candidate model text to gather evidence (short quote) and source metadata

### Step 2 — Generate Candidates
- Query predefined internet sources
- Extract candidate structured values
- Prefer external rule matches when available

### Step 3 — Score Candidates
- Apply scoring model
- Calculate confidence (0..1)

### Step 4 — Apply Decision Rules
- If confidence >= 0.80 → overwrite
- Otherwise → preserve original

### Step 5 — Output Results
- Persist results with audit fields
- Record `source_url` and `evidence_quote` from the matched rule when using the external ruleset
- Record supplemental AI-derived fields such as `ai_vendor_hint`, `ai_model_hint`, `ai_confidence`, `ai_reason`, and `ai_source` as non-authoritative enrichment metadata
- When evidence is found on an external source, slightly boost the candidate confidence proportional to evidence quality and the configured source confidence

Note: The previous standalone `reference_validator` utility has been removed; its responsibilities (fetching reference pages and checking model presence) are integrated into the parsing step and recorded in the output for auditability.

## 6. Error Handling
- Missing data → mark UNKNOWN
- No candidates → confidence = 0
- Ambiguous matches → reduced confidence

## 7. Constraints
- Must be deterministic
- Must be auditable
- Must not hallucinate

## 8. Reviewer SOP — Triage Playbook

### Scope
- Apply this playbook only to rows where `action` is `SUGGEST_ONLY` or `NO_CHANGE`.
- `APPLY_CHANGE` rows do not require manual triage unless flagged by QA.

### Required Checks (in order)
1. Verify `input_raw` is complete and not truncated.
2. Verify `vendor_hint` and `model_hint` against approved source evidence.
3. Confirm `source_url` is valid and `evidence_quote` supports the proposed value.
4. Review `ai_*` fields as supplemental context only.
5. Confirm proposed change does not violate known aliases or override policy.

### Triage Rules
1. `SUGGEST_ONLY`:
  - Approve into override when evidence is clear and specific.
  - Otherwise keep original value and mark for follow-up.
2. `NO_CHANGE`:
  - Do not overwrite by default.
  - Only approve override when two independent checks agree: source evidence and internal naming rules.

### Reviewer Output Actions
1. If approved: add row to `data/input/override.csv` with a short `comment` citing evidence.
2. If rejected: keep original output and log reason as `REVIEW_REJECTED_INSUFFICIENT_EVIDENCE`.
3. If unknown: log `REVIEW_UNKNOWN` and leave canonical fields unchanged.

### Audit Requirements
- Every manual approval must include evidence notes in override `comment`.
- Reviewer decisions must be reproducible from saved source and quoted text.