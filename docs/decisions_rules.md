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
- AI-derived fields are supplemental and must not replace the canonical parse decision

## 3. Confidence Components
Final confidence is composed of:
- vendor_match_score
- model_match_score
- version_match_score
- source_quality_score
- evidence_quality_score

Note: When a manufacturer `source_url` is available, the parser will attempt to fetch the page and extract short evidence quotes. The parser can use that evidence to refine the inferred `vendor_hint`, `model_hint`, and `version_hint` before the final confidence is computed.
The `source_quality_score` and `evidence_quality_score` are derived from the configured source `confidence` and the presence/quality of extracted matches; evidence may boost the final confidence, but the pipeline still only overwrites input when the final decision is `APPLY_CHANGE`.

Manual override rules are always trusted when matched, and they are assigned confidence `1.00` with `source_url` set to `OVERRIDE_RULESET`.

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