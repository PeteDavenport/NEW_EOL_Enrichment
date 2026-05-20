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
- External reference ruleset directory containing canonical rule files (`.csv` or `.json`)

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
- Consult external reference ruleset for exact pattern matches

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

## 6. Error Handling
- Missing data → mark UNKNOWN
- No candidates → confidence = 0
- Ambiguous matches → reduced confidence

## 7. Constraints
- Must be deterministic
- Must be auditable
- Must not hallucinate