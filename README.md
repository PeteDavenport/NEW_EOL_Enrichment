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

## Manual Override Rules
The pipeline also supports an optional manual override CSV file.
- The override file should contain columns: `input_raw`, `vendor_hint`, `model_hint`, `version_hint`, and optional `comment`.
- Overrides are matched against the normalized raw input string.
- When an override is found, the parser applies the manual hints with confidence `1.00` and records `source_url` as `OVERRIDE_RULESET`.
- This is useful for fixing local ruleset values or tweaking parsed values manually.

You can pass the override file with:

```bash
python -m pipeline.cli --input data/input/input.csv --output data/output/parsed.csv --reference-dir data/reference --override-file data/input/override.csv
```

If you want the default automatic override file location, place `override.csv` under `data/input/` and the CLI will use `data/input/override.csv` by default.

Breaking into small parts and using Policies
