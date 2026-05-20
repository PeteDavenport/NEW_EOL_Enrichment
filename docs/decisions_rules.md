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