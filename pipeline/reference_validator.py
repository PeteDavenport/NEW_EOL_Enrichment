import argparse
import csv
import re
import ssl
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pipeline.parse import detect_vendor

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"


@dataclass
class ReferenceSource:
    manufacturer: str
    source_url: str
    source_type: str
    confidence: Optional[float] = None


def load_reference_sources(reference_dir: Path) -> List[ReferenceSource]:
    sources: List[ReferenceSource] = []
    if not reference_dir.exists() or not reference_dir.is_dir():
        return sources

    for path in sorted(reference_dir.iterdir()):
        if path.suffix.lower() != '.csv':
            continue
        with path.open(newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            for item in reader:
                manufacturer = str(item.get('manufacturer', '')).strip()
                source_url = str(item.get('source_url', '')).strip()
                if not manufacturer or not source_url:
                    continue
                confidence = None
                try:
                    confidence = float(item.get('confidence', '') or '')
                except ValueError:
                    confidence = None
                sources.append(
                    ReferenceSource(
                        manufacturer=manufacturer,
                        source_url=source_url,
                        source_type=str(item.get('source_type', 'manufacturer')).strip() or 'manufacturer',
                        confidence=confidence,
                    )
                )
    return sources


def load_input_models(path: Path) -> List[str]:
    models: List[str] = []
    with path.open(newline='', encoding='utf-8-sig') as fh:
        reader = csv.reader(fh)
        rows = [row for row in reader if row]
    if rows and rows[0] and rows[0][0].strip().lower() == 'model':
        rows = rows[1:]
    for row in rows:
        value = row[0].strip()
        if value:
            models.append(value)
    return models


def fetch_url_text(url: str, timeout: int = 20) -> Optional[str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            charset = response.headers.get_content_charset() or 'utf-8'
            data = response.read()
            return data.decode(charset, errors='replace')
    except (HTTPError, URLError, ValueError):
        return None


def normalise_text(text: str) -> str:
    text = text or ''
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def search_model_in_page(model: str, page_text: str) -> bool:
    return normalise_text(model) in normalise_text(page_text)


def validate_models(input_models: List[str], sources: List[ReferenceSource]) -> List[Dict[str, str]]:
    sources_by_vendor = defaultdict(list)
    for source in sources:
        sources_by_vendor[source.manufacturer.lower()].append(source)

    results: List[Dict[str, str]] = []
    for model in input_models:
        vendor = detect_vendor(model)
        vendor_sources = sources_by_vendor.get(vendor.lower(), [])
        if not vendor_sources:
            results.append({
                'input_raw': model,
                'vendor': vendor,
                'source_url': '',
                'source_type': '',
                'source_confidence': '',
                'found': 'NO_SOURCE',
                'note': 'No manufacturer reference available',
            })
            continue

        for source in sorted(vendor_sources, key=lambda s: s.confidence or 0.0, reverse=True):
            page_text = fetch_url_text(source.source_url)
            if page_text is None:
                found = 'UNREACHABLE'
                note = 'Could not fetch reference URL'
            else:
                found = 'YES' if search_model_in_page(model, page_text) else 'NO'
                note = 'Model string found on page' if found == 'YES' else 'Model string not found on page'

            results.append({
                'input_raw': model,
                'vendor': vendor,
                'source_url': source.source_url,
                'source_type': source.source_type,
                'source_confidence': f'{source.confidence:.2f}' if source.confidence is not None else '',
                'found': found,
                'note': note,
            })
    return results


def write_validation_report(path: Path, records: List[Dict[str, str]]) -> None:
    if not records:
        return
    fieldnames = list(records[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser(description='Validate hardware reference naming conventions against external reference URLs.')
    parser.add_argument('--input', default='data/input/input.csv', help='Path to the input CSV file.')
    parser.add_argument('--reference-dir', default='data/reference', help='Directory containing manufacturer reference rules.')
    parser.add_argument('--output', default='data/output/reference_validation.csv', help='Path to the validation report CSV.')
    args = parser.parse_args()

    models = load_input_models(Path(args.input))
    sources = load_reference_sources(Path(args.reference_dir))
    report = validate_models(models, sources)
    write_validation_report(Path(args.output), report)
    print(f'Validated {len(models)} models against {len(sources)} reference sources and wrote report to {args.output}')


if __name__ == '__main__':
    main()
