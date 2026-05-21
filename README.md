# NEW_EOL_Enrichment
A new more intelligent attempt at enrichment

This repository normalises raw hardware model strings into structured vendor, model, and version values with confidence scoring and auditability.

## External Reference Ruleset
The pipeline now supports a manufacturer-level external reference ruleset in `data/reference/`.
- `data/reference/hardware_reference_rules.csv` now contains `manufacturer`, `source_url`, `source_type`, and `confidence`.
- The parser uses the vendor hint from raw input to select matching reference sources.
- Direct manufacturer sources are prioritized; third-party sources may be consulted when the manufacturer source is insufficient.
- The selected source URL and rule confidence are recorded in output fields.

## Reference Evidence
The parser now automatically fetches the configured `source_url` for a detected manufacturer when available, extracts short evidence quotes when the inferred model matches page content, and adjusts the confidence based on evidence quality and source confidence.
- Extracted evidence can improve the inferred `vendor_hint`, `model_hint`, and `version_hint` before the final decision is made.
- The parser still only applies a normalized change when the final confidence reaches the `APPLY_CHANGE` threshold.
- The previous separate `reference_validator` script has been removed — validation and evidence extraction are performed during parsing and recorded in output fields such as `source_url`, `evidence_quote`, and `third_party_result`.

## Usage
Run the pipeline with the default reference directory:

```bash
python -m pipeline.cli --input data/input/input.csv --output data/output/parsed.csv --reference-dir data/reference
```

The `--reference-dir` option can point to any directory containing external source files.

Breaking into small parts and using Policies
