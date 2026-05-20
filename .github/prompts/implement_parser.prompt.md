---
description: Implement the parser stage from SOP
---

# Context
Read:
- docs/SOP.md
- docs/decision_rules.md

# Task
Implement Step 1 — Parse Input

# Requirements
- Clean string
- Tokenise into list
- Extract:
  - vendor_hint
  - model_hint
  - version_hint

# Constraints
- Deterministic only
- No internet usage
- No guessing

# Output
- Python function in pipeline/parse.py
- Minimal code only