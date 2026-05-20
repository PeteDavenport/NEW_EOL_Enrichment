import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import time
try:
    import requests
except Exception:
    requests = None
import urllib.request
from html import unescape

VENDOR_ALIASES = {
    "dell": "Dell",
    "dell emc": "Dell EMC",
    "hp": "Hewlett Packard",
    "hewlett packard": "Hewlett Packard",
    "hewlett packard enterprise": "Hewlett Packard",
    "hpe": "Hewlett Packard",
    "cisco": "Cisco",
    "juniper": "Juniper",
    "palo alto networks": "Palo Alto Networks",
    "palo alto": "Palo Alto Networks",
    "f5": "F5",
    "brocade": "Brocade",
    "sun": "Oracle Sun",
    "oracle": "Oracle",
    "arista": "Arista",
    "qnap": "Qnap",
    "mellanox": "Mellanox",
    "alcatel lucent": "Alcatel Lucent",
    "alcatel": "Alcatel",
    "mcafee": "McAfee",
    "super micro": "Super Micro",
    "ibm": "IBM",
    "hewlett packard proliant": "Hewlett Packard",
    "hewlett packard storageworks": "Hewlett Packard",
}
KNOWN_VENDORS = sorted(VENDOR_ALIASES.keys(), key=len, reverse=True)


@dataclass
class ReferenceRule:
    manufacturer: str
    source_url: str
    source_type: str
    confidence: Optional[float] = None


def normalise_text(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str) -> List[str]:
    return text.split()


def load_reference_rules(reference_dir: Path) -> List[ReferenceRule]:
    rules: List[ReferenceRule] = []
    if not reference_dir.exists() or not reference_dir.is_dir():
        return rules

    for path in sorted(reference_dir.iterdir()):
        if path.suffix.lower() == '.json':
            rules.extend(_load_rules_from_json(path))
        elif path.suffix.lower() == '.csv':
            rules.extend(_load_rules_from_csv(path))
    return rules


def _load_rules_from_json(path: Path) -> List[ReferenceRule]:
    rules: List[ReferenceRule] = []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return rules

    if isinstance(data, dict):
        data = [data]

    for item in data:
        manufacturer = str(item.get('manufacturer', '')).strip()
        source_url = str(item.get('source_url', '')).strip()
        if not manufacturer or not source_url:
            continue
        rules.append(_build_reference_rule(item, path))
    return rules


def _load_rules_from_csv(path: Path) -> List[ReferenceRule]:
    rules: List[ReferenceRule] = []
    try:
        with path.open(newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            for item in reader:
                manufacturer = str(item.get('manufacturer', '')).strip()
                source_url = str(item.get('source_url', '')).strip()
                if not manufacturer or not source_url:
                    continue
                rules.append(_build_reference_rule(item, path))
    except OSError:
        return rules
    return rules


def _build_reference_rule(item: Dict[str, str], path: Path) -> ReferenceRule:
    raw_confidence = item.get('confidence', '')
    confidence: Optional[float] = None
    try:
        confidence = float(raw_confidence) if raw_confidence else None
    except ValueError:
        confidence = None

    source_url = str(item.get('source_url', '')).strip()
    if not source_url:
        source_url = path.resolve().as_uri()

    return ReferenceRule(
        manufacturer=str(item.get('manufacturer', '')).strip(),
        source_url=source_url,
        source_type=str(item.get('source_type', 'manufacturer')).strip() or 'manufacturer',
        confidence=confidence,
    )


def detect_vendor(text: str) -> str:
    text_lower = normalise_text(text)
    for alias in KNOWN_VENDORS:
        if alias in text_lower:
            return VENDOR_ALIASES[alias]
    return "UNKNOWN"


def extract_version(text: str) -> str:
    patterns = [
        r'\b(gen\s?\d{1,2})\b',
        r'\b(asa[-_ ]?\d{3,4})\b',
        r'\b(pa[-_ ]?\d{3,4})\b',
        r'\b(\d{3,4}[a-zA-Z]?(-[a-zA-Z0-9]+)?)\b',
    ]
    text_lower = normalise_text(text)
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            candidate = match.group(1).strip()
            return candidate.upper()
    return "UNKNOWN"


def strip_vendor_and_version(text: str, vendor: str, version: str) -> str:
    working = normalise_text(text)
    if vendor != "UNKNOWN":
        for alias, canonical in VENDOR_ALIASES.items():
            if canonical == vendor:
                working = working.replace(alias, " ")
    if version != "UNKNOWN":
        working = working.replace(version.lower(), " ")
    working = re.sub(r'\b(switch|router|server|firewall|appliance|storage|system|fabric|enclosure|module|rack|blade|series|integrated|services|high|density|data|center|unit)\b', ' ', working)
    working = re.sub(r'\s+', ' ', working).strip()
    return working if working else "UNKNOWN"


def score_confidence(vendor: str, model: str, version: str) -> float:
    score = 0.0
    score += 0.35 if vendor != "UNKNOWN" else 0.0
    score += 0.35 if model != "UNKNOWN" else 0.0
    score += 0.20 if version != "UNKNOWN" else 0.0
    score += 0.10 if vendor != "UNKNOWN" and model != "UNKNOWN" else 0.0
    return min(1.0, score)


def _fetch_text_from_url(url: str, timeout: int = 6) -> Optional[str]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; HWNorm/1.0)"}
    try:
        if requests:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                return resp.text
            return None
        # fallback to urllib
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            raw = fh.read()
            try:
                return raw.decode('utf-8', errors='ignore')
            except Exception:
                return raw.decode('latin-1', errors='ignore')
    except Exception:
        return None


def _strip_html(text: str) -> str:
    # Very small utility to remove tags and collapse whitespace
    text = re.sub(r'<script.*?>.*?</script>', ' ', text, flags=re.I | re.S)
    text = re.sub(r'<style.*?>.*?</style>', ' ', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _find_model_evidence(model: str, page_text: str) -> (Optional[str], float):
    """
    Search page_text for the model string. Return a short evidence quote and a quality score (0..1).
    """
    if not model or model == "UNKNOWN":
        return None, 0.0

    model_norm = normalise_text(model)
    page_norm = normalise_text(_strip_html(page_text))

    # Exact phrase match has high quality
    if model_norm in page_norm:
        idx = page_norm.find(model_norm)
        start = max(0, idx - 80)
        end = min(len(page_norm), idx + len(model_norm) + 80)
        snippet = page_norm[start:end]
        return snippet, 0.90

    # token overlap
    tokens = [t for t in tokenize(model_norm) if len(t) > 2]
    if not tokens:
        return None, 0.0

    found = [t for t in tokens if t in page_norm]
    if found:
        # evidence quality proportional to fraction of tokens found
        frac = len(found) / len(tokens)
        score = 0.40 + 0.50 * frac
        # build small quote from first found token
        t = found[0]
        idx = page_norm.find(t)
        start = max(0, idx - 60)
        end = min(len(page_norm), idx + len(t) + 60)
        snippet = page_norm[start:end]
        return snippet, min(1.0, score)

    return None, 0.0


def decision_action(confidence: float) -> Dict[str, str]:
    if confidence >= 0.80:
        return {"action": "APPLY_CHANGE", "reason_code": "CONFIDENCE_HIGH"}
    if confidence >= 0.50:
        return {"action": "SUGGEST_ONLY", "reason_code": "CONFIDENCE_MEDIUM"}
    return {"action": "NO_CHANGE", "reason_code": "CONFIDENCE_LOW"}


def find_reference_source(vendor: str, rules: List[ReferenceRule]) -> Optional[ReferenceRule]:
    matches = [rule for rule in rules if rule.manufacturer and rule.manufacturer.lower() == vendor.lower()]
    if not matches:
        return None
    return max(matches, key=lambda rule: rule.confidence or 0.0)


def parse_row(input_raw: str, reference_rules: Optional[List[ReferenceRule]] = None) -> Dict[str, str]:
    reference_rules = reference_rules or []
    vendor_hint = detect_vendor(input_raw)
    reference_source = find_reference_source(vendor_hint, reference_rules)
    version_hint = extract_version(input_raw)
    model_hint = strip_vendor_and_version(input_raw, vendor_hint, version_hint)
    confidence = score_confidence(vendor_hint, model_hint, version_hint)

    # If we have a reference source for the detected vendor, try to confirm the model
    if reference_source:
        source_url = reference_source.source_url
        evidence_quote = ""
        try:
            page_text = _fetch_text_from_url(source_url)
            if page_text:
                snippet, evidence_score = _find_model_evidence(model_hint, page_text)
                if snippet and evidence_score > 0.0:
                    # boost confidence slightly based on evidence and source quality
                    src_conf = reference_source.confidence or 0.0
                    boost = evidence_score * src_conf * 0.10
                    confidence = min(1.0, confidence + boost)
                    evidence_quote = snippet
                else:
                    # no evidence found on page; keep source recorded but no quote
                    evidence_quote = ""
            else:
                evidence_quote = ""
        except Exception:
            evidence_quote = ""
    else:
        source_url = "LOCAL_RULESET"
        evidence_quote = model_hint if model_hint != "UNKNOWN" else ""

    action_info = decision_action(confidence)
    parse_applied = action_info["action"] == "APPLY_CHANGE"

    return {
        "input_raw": input_raw,
        "normalised_raw": normalise_text(input_raw),
        "vendor_hint": vendor_hint,
        "model_hint": model_hint,
        "version_hint": version_hint,
        "source_url": source_url,
        "evidence_quote": evidence_quote,
        "confidence": f"{confidence:.2f}",
        "action": action_info["action"],
        "reason_code": action_info["reason_code"],
        "parse_applied": str(parse_applied),
        "output_value": model_hint if parse_applied else input_raw,
    }
