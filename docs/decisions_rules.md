# Decision Rules — Hardware Normalisation

## 1. Confidence Thresholds
- >= 0.80 → APPLY CHANGE
- 0.50–0.79 → SUGGEST ONLY (do not overwrite)
- < 0.50 → NO CHANGE

## 2. Non-Negotiable Rules
- Never invent vendor, model, or version
- Never overwrite input if confidence < 0.80
- Always produce reason_code
- Always include evidence if available

## 3. Confidence Components
Final confidence is composed of:
- vendor_match_score
- model_match_score
- version_match_score
- source_quality_score
- evidence_quality_score

Note: When a manufacturer `source_url` is available, the parser will attempt to fetch the page and extract short evidence quotes. The `source_quality_score` and `evidence_quality_score` are derived from the configured source `confidence` and the presence/quality of extracted matches; evidence may slightly boost the final confidence but will not cause non-deterministic overwrites.

## 4. Determinism
Given same:
- input
- sources
- cache

→ Output must NOT change

## 5. Allowed Sources
Must be explicit and recorded:
- URL
- retrieval timestamp (optional later)
- extracted evidence text

## 6. Unknown Handling
If data missing:
- return "UNKNOWN"
- do not guess