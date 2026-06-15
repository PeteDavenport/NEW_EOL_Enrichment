import argparse
import csv
from pathlib import Path
from typing import Dict, List

try:
    from pipeline.parse import normalise_text
except Exception:
    from parse import normalise_text

PENDING_STATUS = "PENDING_REVIEW"

ALLOWED_REVIEW_CODES = {
    "REVIEW_PENDING",
    "REVIEW_APPROVED_OVERRIDE",
    "REVIEW_REJECTED_INSUFFICIENT_EVIDENCE",
    "REVIEW_REJECTED_RULE_CONFLICT",
    "REVIEW_UNKNOWN",
    "NOT_REQUIRED",
}

OVERRIDE_FIELDS = ["input_raw", "vendor_hint", "model_hint", "version_hint", "comment"]


def read_csv_records(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv_records(path: Path, fieldnames: List[str], records: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def export_pending(parsed_file: Path, output_file: Path) -> int:
    rows = read_csv_records(parsed_file)
    pending: List[Dict[str, str]] = []

    for row in rows:
        review_required = str(row.get("review_required", "")).strip().lower() == "true"
        review_status = str(row.get("review_queue_status", "")).strip()
        if not review_required and review_status != PENDING_STATUS:
            continue

        out_row = dict(row)
        out_row["reviewer_decision_code"] = row.get("review_decision_code", "REVIEW_PENDING") or "REVIEW_PENDING"
        out_row["reviewer_comment"] = ""
        out_row["approved_vendor_hint"] = ""
        out_row["approved_model_hint"] = ""
        out_row["approved_version_hint"] = ""
        pending.append(out_row)

    if not pending:
        # Keep a template with at least expected columns.
        fieldnames = [
            "input_raw",
            "action",
            "confidence",
            "review_required",
            "review_queue_status",
            "review_recommendation",
            "review_gate",
            "review_decision_code",
            "reviewer_decision_code",
            "reviewer_comment",
            "approved_vendor_hint",
            "approved_model_hint",
            "approved_version_hint",
        ]
        write_csv_records(output_file, fieldnames, [])
        return 0

    base_fields = list(pending[0].keys())
    write_csv_records(output_file, base_fields, pending)
    return len(pending)


def load_override_index(override_file: Path) -> Dict[str, Dict[str, str]]:
    rows = read_csv_records(override_file)
    index: Dict[str, Dict[str, str]] = {}
    for row in rows:
        input_raw = str(row.get("input_raw", "")).strip()
        if not input_raw:
            continue
        index[normalise_text(input_raw)] = {
            "input_raw": input_raw,
            "vendor_hint": str(row.get("vendor_hint", "")).strip() or "UNKNOWN",
            "model_hint": str(row.get("model_hint", "")).strip() or "UNKNOWN",
            "version_hint": str(row.get("version_hint", "")).strip() or "UNKNOWN",
            "comment": str(row.get("comment", "")).strip(),
        }
    return index


def build_override_comment(reviewer_comment: str, evidence_quote: str) -> str:
    reviewer_comment = (reviewer_comment or "").strip()
    evidence_quote = (evidence_quote or "").strip()
    if reviewer_comment and evidence_quote:
        return f"REVIEW_APPROVED_OVERRIDE | {reviewer_comment} | evidence: {evidence_quote[:160]}"
    if reviewer_comment:
        return f"REVIEW_APPROVED_OVERRIDE | {reviewer_comment}"
    if evidence_quote:
        return f"REVIEW_APPROVED_OVERRIDE | evidence: {evidence_quote[:160]}"
    return "REVIEW_APPROVED_OVERRIDE"


def apply_decisions(
    review_file: Path,
    override_file: Path,
    dry_run: bool = False,
) -> Dict[str, int]:
    review_rows = read_csv_records(review_file)
    overrides = load_override_index(override_file)

    approved_count = 0
    upserted_count = 0
    skipped_count = 0

    for row in review_rows:
        decision_code = str(row.get("reviewer_decision_code", row.get("review_decision_code", "REVIEW_PENDING"))).strip() or "REVIEW_PENDING"
        if decision_code not in ALLOWED_REVIEW_CODES:
            raise ValueError(f"Unsupported reviewer decision code: {decision_code}")

        if decision_code != "REVIEW_APPROVED_OVERRIDE":
            skipped_count += 1
            continue

        reviewer_comment = str(row.get("reviewer_comment", "")).strip()
        if not reviewer_comment:
            input_raw = str(row.get("input_raw", "")).strip()
            raise ValueError(
                "reviewer_comment is required for REVIEW_APPROVED_OVERRIDE"
                + (f" (input_raw={input_raw})" if input_raw else "")
            )

        input_raw = str(row.get("input_raw", "")).strip()
        if not input_raw:
            skipped_count += 1
            continue

        vendor_hint = str(row.get("approved_vendor_hint", "")).strip() or str(row.get("vendor_hint", "")).strip() or "UNKNOWN"
        model_hint = str(row.get("approved_model_hint", "")).strip() or str(row.get("model_hint", "")).strip() or "UNKNOWN"
        version_hint = str(row.get("approved_version_hint", "")).strip() or str(row.get("version_hint", "")).strip() or "UNKNOWN"

        if vendor_hint == "" or model_hint == "":
            skipped_count += 1
            continue

        comment = build_override_comment(
            reviewer_comment,
            str(row.get("evidence_quote", "")),
        )

        key = normalise_text(input_raw)
        overrides[key] = {
            "input_raw": input_raw,
            "vendor_hint": vendor_hint,
            "model_hint": model_hint,
            "version_hint": version_hint,
            "comment": comment,
        }
        approved_count += 1
        upserted_count += 1

    if not dry_run:
        ordered = sorted(overrides.values(), key=lambda r: normalise_text(r["input_raw"]))
        write_csv_records(override_file, OVERRIDE_FIELDS, ordered)

    return {
        "review_rows": len(review_rows),
        "approved_rows": approved_count,
        "upserted_rows": upserted_count,
        "skipped_rows": skipped_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Review queue utility for deterministic triage workflow.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export-pending", help="Export pending review rows from parsed output.")
    export_parser.add_argument("--parsed-file", default="data/output/parsed.csv", help="Parsed CSV source file.")
    export_parser.add_argument("--output-file", default="data/output/review_queue.csv", help="Output review queue CSV file.")

    apply_parser = subparsers.add_parser("apply-decisions", help="Apply approved reviewer decisions into override CSV.")
    apply_parser.add_argument("--review-file", default="data/output/review_queue.csv", help="Reviewer decisions CSV file.")
    apply_parser.add_argument("--override-file", default="data/input/override.csv", help="Override CSV to update.")
    apply_parser.add_argument("--dry-run", action="store_true", help="Validate and count updates without writing override file.")

    args = parser.parse_args()

    if args.command == "export-pending":
        count = export_pending(Path(args.parsed_file), Path(args.output_file))
        print(f"Exported {count} pending review rows to {args.output_file}")
        return

    if args.command == "apply-decisions":
        summary = apply_decisions(
            review_file=Path(args.review_file),
            override_file=Path(args.override_file),
            dry_run=args.dry_run,
        )
        mode = "DRY_RUN" if args.dry_run else "APPLIED"
        print(
            f"{mode}: review_rows={summary['review_rows']} approved_rows={summary['approved_rows']} "
            f"upserted_rows={summary['upserted_rows']} skipped_rows={summary['skipped_rows']}"
        )
        return


if __name__ == "__main__":
    main()
