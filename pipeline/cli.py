import argparse
import csv
from pathlib import Path

from pipeline.parse import load_override_rules, load_reference_rules, normalise_text, parse_row


def load_input(path: Path) -> list[str]:
    with path.open(newline='', encoding='utf-8') as fh:
        reader = csv.reader(fh)
        rows = [row for row in reader if row]
    if rows and rows[0] and rows[0][0].strip().lower() == 'model':
        rows = rows[1:]
    return [row[0].strip() for row in rows if row and row[0].strip()]


def sort_rows(rows: list[str]) -> list[str]:
    return sorted(rows, key=lambda value: normalise_text(value))


def write_output(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'input_raw',
        'normalised_raw',
        'vendor_hint',
        'model_hint',
        'version_hint',
        'source_url',
        'evidence_quote',
        'third_party_result',
        'confidence',
        'action',
        'reason_code',
        'parse_applied',
        'output_value',
    ]
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser(description='Sort and parse hardware input CSV data.')
    parser.add_argument(
        '--input',
        default='data/input/input.csv',
        help='Path to the input CSV file.',
    )
    parser.add_argument(
        '--output',
        default='data/output/parsed.csv',
        help='Path to the output CSV file.',
    )
    parser.add_argument(
        '--reference-dir',
        default='data/reference',
        help='Directory containing external reference rulesets (.json or .csv).',
    )
    parser.add_argument(
        '--override-file',
        default='data/input/override.csv',
        help='Optional CSV file containing manual override hints.',
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    reference_dir = Path(args.reference_dir)
    override_file = Path(args.override_file) if args.override_file else None

    rows = load_input(input_path)
    rules = load_reference_rules(reference_dir)
    override_rules = load_override_rules(override_file) if override_file else {}
    sorted_rows = sort_rows(rows)
    records = [parse_row(value, rules, override_rules) for value in sorted_rows]
    write_output(output_path, records)
    print(f'Parsed {len(records)} rows with {len(rules)} reference rules and wrote sorted output to {output_path}')


if __name__ == '__main__':
    main()
