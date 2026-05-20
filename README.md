# NEW_EOL_Enrichment
A new more intelligent attempt at enrichment

This repository normalises raw hardware model strings into structured vendor, model, and version values with confidence scoring and auditability.

## External Reference Ruleset
The pipeline now supports a manufacturer-level external reference ruleset in `data/reference/`.
- `data/reference/hardware_reference_rules.csv` now contains `manufacturer`, `source_url`, `source_type`, and `confidence`.
- Direct manufacturer sources are prioritized and third-party sources are included with lower confidence.
- The parser uses the vendor hint from the raw input and attaches the matching external reference URL.

## Validation Script
A validator script is available for confirming naming conventions from external reference sites:

```bash
python -m pipeline.reference_validator --input data/input/input.csv --reference-dir data/reference --output data/output/reference_validation.csv
```

This produces a CSV report showing which input models were found on each reference location.

## Usage
Run the pipeline with the default reference directory:

```bash
python -m pipeline.cli --input data/input/input.csv --output data/output/parsed.csv --reference-dir data/reference
```

The `--reference-dir` option can point to any directory containing external source files.

Breaking into small parts and using Policies
