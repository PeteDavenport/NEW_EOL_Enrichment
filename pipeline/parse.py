import csv
import json
import re
import os
import logging
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

from ai_vendor_enricher import AIVendorEnricher, AIEnrichmentResult

logger = logging.getLogger(__name__)

# Global AI enricher instance (lazy-initialized)
_ai_enricher: Optional[AIVendorEnricher] = None

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


@dataclass
class OverrideRule:
    input_raw: str
    normalised_raw: str
    vendor_hint: str
    model_hint: str
    version_hint: str
    comment: str = ""


def _init_ai_enricher() -> AIVendorEnricher:
    """
    Initialize the global AI enricher on first use using GitHub Copilot.
    Respects environment variables for API key and model configuration.
    Falls back to deterministic enrichment if no API key is provided.
    """
    global _ai_enricher
    if _ai_enricher is not None:
        return _ai_enricher

    api_key = os.environ.get("COPILOT_API_KEY")
    model = os.environ.get("COPILOT_MODEL", "gpt-4")
    cache_dir = Path(os.environ.get("AI_CACHE_DIR", ".cache/ai_vendor_enricher"))
    enable_cache = os.environ.get("AI_CACHE_ENABLED", "true").lower() == "true"

    _ai_enricher = AIVendorEnricher(
        api_key=api_key,
        model=model,
        cache_dir=cache_dir,
        enable_cache=enable_cache,
        fallback_func=_deterministic_enrich_vendor_model,
    )

    if api_key:
        logger.info(f"AI enricher initialized with GitHub Copilot/{model}")
    else:
        logger.info("AI enricher initialized in DETERMINISTIC_FALLBACK mode (no API key)")

    return _ai_enricher


def _deterministic_enrich_vendor_model(
    input_raw: str,
    vendor_hint: str,
    model_hint: str,
    version_hint: str,
    reference_rules: Optional[List[ReferenceRule]] = None,
) -> AIEnrichmentResult:
    """
    Original deterministic vendor/model enrichment.
    Used as fallback when AI is unavailable.
    """
    reference_rules = reference_rules or []
    ai_vendor_hint = vendor_hint
    ai_model_hint = model_hint
    ai_confidence = 0.0
    ai_reason = "NO_AI_ACTION"
    ai_source = "AGENT_VENDOR_MODEL"

    input_norm = normalise_text(input_raw)
    if ai_vendor_hint == "UNKNOWN":
        for rule in reference_rules:
            manufacturer_norm = normalise_text(rule.manufacturer)
            if manufacturer_norm and manufacturer_norm in input_norm:
                ai_vendor_hint = rule.manufacturer
                ai_reason = "REFERENCE_MANUFACTURER_MATCH"
                ai_source = rule.source_url
                ai_confidence = 0.45
                break

    if ai_model_hint == "UNKNOWN" and ai_vendor_hint != "UNKNOWN":
        candidate = strip_vendor_and_version(input_raw, ai_vendor_hint, version_hint)
        if candidate != "UNKNOWN":
            ai_model_hint = candidate
            if ai_reason == "NO_AI_ACTION":
                ai_reason = "MODEL_FROM_CLEANED_TEXT"
            ai_confidence = max(ai_confidence, 0.55)
            ai_source = ai_source or "AGENT_VENDOR_MODEL"

    if ai_vendor_hint != "UNKNOWN" and ai_model_hint != "UNKNOWN":
        ai_confidence = max(ai_confidence, 0.70)

    return AIEnrichmentResult(
        ai_vendor_hint=ai_vendor_hint,
        ai_model_hint=ai_model_hint,
        ai_confidence=ai_confidence,
        ai_reason=ai_reason,
        ai_source=ai_source,
    )


def ai_enrich_vendor_model(
    input_raw: str,
    vendor_hint: str,
    model_hint: str,
    version_hint: str,
    reference_rules: Optional[List[ReferenceRule]] = None,
) -> AIEnrichmentResult:
    """
    Enrich vendor/model using AI with deterministic fallback and audit controls.

    This function uses the global AI enricher, which:
    - Attempts LLM-based enrichment (if API key configured)
    - Falls back to deterministic logic if LLM unavailable
    - Caches results for determinism
    - Records all decisions for auditability

    All returned fields are supplemental and non-authoritative.
    The canonical decision is made separately based on confidence thresholds.

    Args:
        input_raw: Raw hardware string
        vendor_hint: Current vendor guess (from deterministic parse)
        model_hint: Current model guess (from deterministic parse)
        version_hint: Current version guess (from deterministic parse)
        reference_rules: Reference rules (passed to fallback for context)

    Returns:
        AIEnrichmentResult with ai_* fields for audit and context
    """
    enricher = _init_ai_enricher()
    result = enricher.enrich(
        input_raw,
        vendor_hint,
        model_hint,
        version_hint,
        reference_rules,
    )
    return result


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


def load_override_rules(override_file: Path) -> Dict[str, OverrideRule]:
    rules: Dict[str, OverrideRule] = {}
    if not override_file.exists() or not override_file.is_file():
        return rules

    try:
        with override_file.open(newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            for item in reader:
                override_rule = _build_override_rule(item)
                if override_rule:
                    rules[override_rule.normalised_raw] = override_rule
    except OSError:
        return {}
    return rules


def _build_override_rule(item: Dict[str, str]) -> Optional[OverrideRule]:
    input_raw = str(item.get('input_raw', '')).strip()
    if not input_raw:
        return None

    vendor_hint = str(item.get('vendor_hint', '')).strip() or ""
    model_hint = str(item.get('model_hint', '')).strip() or ""
    version_hint = str(item.get('version_hint', '')).strip() or ""
    comment = str(item.get('comment', '')).strip() or ""

    return OverrideRule(
        input_raw=input_raw,
        normalised_raw=normalise_text(input_raw),
        vendor_hint=vendor_hint,
        model_hint=model_hint,
        version_hint=version_hint,
        comment=comment,
    )


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


def _find_version_candidates(text: str) -> List[str]:
    text_lower = normalise_text(text)
    patterns = [
        r'\bgen\s?\d{1,2}\b',
        r'\basa[-_ ]?\d{3,4}\b',
        r'\bpa[-_ ]?\d{3,4}\b',
        r'\b\d{3,4}[a-zA-Z]?(?:-[a-zA-Z0-9]+)?\b',
    ]
    candidates: List[str] = []
    for pattern in patterns:
        candidates.extend(re.findall(pattern, text_lower))
    return [candidate.upper() for candidate in candidates if candidate]


def _choose_best_version_candidate(current_version: str, candidates: List[str]) -> str:
    if not candidates:
        return current_version

    current_version = current_version.upper() if current_version else "UNKNOWN"
    if current_version == "UNKNOWN":
        return candidates[0]

    if current_version in candidates:
        return current_version

    def candidate_score(version: str) -> tuple[int, int]:
        return (
            1 if re.search(r'[A-Z\-]', version) else 0,
            len(version),
        )

    best_candidate = max(candidates, key=candidate_score)
    if candidate_score(best_candidate) > candidate_score(current_version):
        return best_candidate

    return current_version


def _update_hints_from_evidence(vendor_hint: str, model_hint: str, version_hint: str, evidence_quote: str) -> tuple[str, str, str]:
    if not evidence_quote:
        return vendor_hint, model_hint, version_hint

    improved_vendor = detect_vendor(evidence_quote)
    if improved_vendor == "UNKNOWN":
        improved_vendor = vendor_hint

    improved_version = _choose_best_version_candidate(version_hint, _find_version_candidates(evidence_quote))
    improved_model = strip_vendor_and_version(evidence_quote, improved_vendor, improved_version)

    if improved_model == "UNKNOWN":
        improved_model = model_hint

    return improved_vendor, improved_model, improved_version


def decision_action(confidence: float) -> Dict[str, str]:
    if confidence >= 0.80:
        return {"action": "APPLY_CHANGE", "reason_code": "CONFIDENCE_HIGH"}
    if confidence >= 0.50:
        return {"action": "SUGGEST_ONLY", "reason_code": "CONFIDENCE_MEDIUM"}
    return {"action": "NO_CHANGE", "reason_code": "CONFIDENCE_LOW"}


def find_reference_source(vendor: str, rules: List[ReferenceRule], source_type: Optional[str] = None) -> Optional[ReferenceRule]:
    matches = [
        rule for rule in rules
        if rule.manufacturer and rule.manufacturer.lower() == vendor.lower()
        and (source_type is None or rule.source_type.lower() == source_type.lower())
    ]
    if not matches:
        return None
    return max(matches, key=lambda rule: rule.confidence or 0.0)


def _evaluate_source_for_model(source: ReferenceRule, model_hint: str) -> tuple[str, float]:
    evidence_quote = ""
    evidence_score = 0.0
    try:
        page_text = _fetch_text_from_url(source.source_url)
        if page_text:
            snippet, evidence_score = _find_model_evidence(model_hint, page_text)
            if snippet and evidence_score > 0.0:
                evidence_quote = snippet
    except Exception:
        evidence_quote = ""
        evidence_score = 0.0
    return evidence_quote, evidence_score


def _apply_evidence_boost(confidence: float, evidence_score: float, source_confidence: float, multiplier: float = 0.10) -> float:
    return min(1.0, confidence + evidence_score * source_confidence * multiplier)


def parse_row(
    input_raw: str,
    reference_rules: Optional[List[ReferenceRule]] = None,
    override_rules: Optional[Dict[str, OverrideRule]] = None,
) -> Dict[str, str]:
    reference_rules = reference_rules or []
    override_rules = override_rules or {}
    normalised_raw = normalise_text(input_raw)

    vendor_hint = detect_vendor(input_raw)
    version_hint = extract_version(input_raw)
    model_hint = strip_vendor_and_version(input_raw, vendor_hint, version_hint)
    confidence = score_confidence(vendor_hint, model_hint, version_hint)
    ai_enrichment = ai_enrich_vendor_model(
        input_raw,
        vendor_hint,
        model_hint,
        version_hint,
        reference_rules,
    )

    # Manual overrides take top priority and are treated as fully trusted.
    override_rule = override_rules.get(normalised_raw)
    if override_rule:
        vendor_hint = override_rule.vendor_hint or vendor_hint
        model_hint = override_rule.model_hint or model_hint
        version_hint = override_rule.version_hint or version_hint
        confidence = 1.0
        source_url = "OVERRIDE_RULESET"
        evidence_quote = override_rule.comment
        third_party_result = "OVERRIDE"
        action_info = {"action": "APPLY_CHANGE", "reason_code": "OVERRIDE"}
        parse_applied = True

        return {
            "input_raw": input_raw,
            "normalised_raw": normalised_raw,
            "vendor_hint": vendor_hint,
            "model_hint": model_hint,
            "version_hint": version_hint,
            "source_url": source_url,
            "evidence_quote": evidence_quote,
            "third_party_result": third_party_result,
            "confidence": f"{confidence:.2f}",
            "action": action_info["action"],
            "reason_code": action_info["reason_code"],
            "parse_applied": str(parse_applied),
            "output_value": model_hint,
            "ai_vendor_hint": ai_enrichment.ai_vendor_hint,
            "ai_model_hint": ai_enrichment.ai_model_hint,
            "ai_confidence": f"{ai_enrichment.ai_confidence:.2f}",
            "ai_reason": ai_enrichment.ai_reason,
            "ai_source": ai_enrichment.ai_source,
        }

    reference_source = find_reference_source(vendor_hint, reference_rules, source_type='manufacturer')
    source_url = "LOCAL_RULESET"
    evidence_quote = ""
    third_party_result = "NOT_CHECKED"

    if reference_source:
        source_url = reference_source.source_url
        evidence_quote, evidence_score = _evaluate_source_for_model(reference_source, model_hint)
        if evidence_score > 0.0:
            vendor_hint, model_hint, version_hint = _update_hints_from_evidence(
                vendor_hint,
                model_hint,
                version_hint,
                evidence_quote,
            )
            confidence = score_confidence(vendor_hint, model_hint, version_hint)
            confidence = _apply_evidence_boost(confidence, evidence_score, reference_source.confidence or 0.0)

        # If the primary manufacturer source still leaves confidence at 0.8 or below,
        # check a third-party vendor page for a stronger confirmation.
        if confidence <= 0.80:
            third_party_source = find_reference_source(vendor_hint, reference_rules, source_type='third_party')
            if third_party_source:
                third_quote, third_score = _evaluate_source_for_model(third_party_source, model_hint)
                if third_quote and third_score >= 0.70:
                    vendor_hint, model_hint, version_hint = _update_hints_from_evidence(
                        vendor_hint,
                        model_hint,
                        version_hint,
                        third_quote,
                    )
                    confidence = score_confidence(vendor_hint, model_hint, version_hint)
                    confidence = max(confidence, 0.85)
                    source_url = third_party_source.source_url
                    evidence_quote = third_quote
                    third_party_result = f"ACCEPTED:{third_quote}"
                elif third_quote and third_score > 0.0:
                    confidence = min(confidence, 0.80)
                    third_party_result = f"REJECTED:{third_quote}"
                else:
                    third_party_result = "REJECTED:NO_EVIDENCE"
    else:
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
        "third_party_result": third_party_result,
        "confidence": f"{confidence:.2f}",
        "action": action_info["action"],
        "reason_code": action_info["reason_code"],
        "parse_applied": str(parse_applied),
        "output_value": model_hint if parse_applied else input_raw,
        "ai_vendor_hint": ai_enrichment.ai_vendor_hint,
        "ai_model_hint": ai_enrichment.ai_model_hint,
        "ai_confidence": f"{ai_enrichment.ai_confidence:.2f}",
        "ai_reason": ai_enrichment.ai_reason,
        "ai_source": ai_enrichment.ai_source,
    }
