# NEW_EOL_Enrichment
A new more intelligent attempt at enrichment

This repository normalises raw hardware model strings into structured vendor, model, and version values with confidence scoring and auditability.

## External Reference Ruleset
The pipeline now supports an external definitive reference ruleset in `data/reference/`.
- `data/reference/hardware_reference_rules.csv` contains exact input patterns and canonical values.
- The CLI loads any `.csv` or `.json` rules from the reference directory.

## Usage
Run the pipeline with the default reference directory:

```bash
python -m pipeline.cli --input data/input/input.csv --output data/output/parsed.csv --reference-dir data/reference
```

The `--reference-dir` option can point to any directory containing external rule files.

Breaking into small parts and using Policies
