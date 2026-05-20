# Copilot Instructions — Hardware Normalisation Project

# TEST RULE

When responding, include the text:
"SOP LOADED

## MANDATORY RULE
Before answering ANY request:
- Read:
  - docs/SOP.md
  - docs/decision_rules.md
  - docs/project_idea.md

If these files are not referenced, STOP and ask for clarification.

## Behaviour
- Follow SOP step-by-step
- Do NOT skip stages
- Do NOT combine stages

## Critical Rules
- Do NOT invent data
- If unsure → return UNKNOWN
- If unknown → return "UNKNOWN"
- Never overwrite unless confidence >= 0.80
- Always include reason_code
- Always follow docs/decision_rules.md exactly

## Coding Rules
- Python only
- Small functions
- Deterministic logic
- No hidden heuristics
- No assumptions

## Output Behaviour
- Prefer structured outputs
- No verbose explanations unless requested