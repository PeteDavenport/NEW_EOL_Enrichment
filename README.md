# NEW_EOL_Enrichment
A new more intelligent attempt at enrichment

This repository normalises raw hardware model strings into structured vendor, model, and version values with confidence scoring and auditability.

## External Reference Ruleset
The pipeline now supports a manufacturer-level external reference ruleset in `data/reference/`.
- `data/reference/hardware_reference_rules.csv` now contains `manufacturer`, `source_url`, `source_type`, and `confidence`.
- Direct manufacturer sources are prioritized and third-party sources are included with lower confidence.
- The parser uses the vendor hint from the raw input and attaches the matching external reference URL.

## Reference Evidence
The parser now automatically fetches the configured `source_url` for a detected manufacturer when available, extracts short evidence quotes when the input model is found on that page, and adjusts the confidence slightly based on the quality of the evidence and the configured source confidence. The previous separate `reference_validator` script has been removed — validation and evidence extraction are performed during parsing and recorded in the output fields `source_url` and `evidence_quote`.

## Usage
Run the pipeline with the default reference directory:

```bash
python -m pipeline.cli --input data/input/input.csv --output data/output/parsed.csv --reference-dir data/reference
```

The `--reference-dir` option can point to any directory containing external source files.

Breaking into small parts and using Policies
