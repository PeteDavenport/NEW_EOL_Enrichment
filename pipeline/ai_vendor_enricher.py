"""
Deterministic vendor/model enrichment wrapper with audit-safe caching.

This module runs with no runtime model API calls. It wraps a deterministic
fallback function and optionally caches supplemental ai_* outputs.
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AIEnrichmentResult:
    """Supplemental enrichment result; never authoritative for final action."""

    ai_vendor_hint: str
    ai_model_hint: str
    ai_confidence: float
    ai_reason: str
    ai_source: str


class AIVendorEnricher:
    """Deterministic enrichment helper with optional result caching."""

    def __init__(
        self,
        fallback_func: Optional[Callable] = None,
        cache_dir: Optional[Path] = None,
        enable_cache: bool = True,
    ) -> None:
        self.fallback_func = fallback_func
        self.enable_cache = enable_cache
        self.cache_dir = cache_dir or Path(".cache/ai_vendor_enricher")

        if self.enable_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, input_raw: str) -> str:
        normalized = (input_raw or "").strip().lower()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"enrichment_{digest}.json"

    def _load_cache(self, input_raw: str) -> Optional[AIEnrichmentResult]:
        if not self.enable_cache:
            return None

        path = self.cache_dir / self._cache_key(input_raw)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result = AIEnrichmentResult(**data)
            result.ai_source = "CACHE"
            return result
        except Exception as exc:
            logger.warning("Failed to read enrichment cache: %s", exc)
            return None

    def _save_cache(self, input_raw: str, result: AIEnrichmentResult) -> None:
        if not self.enable_cache:
            return

        path = self.cache_dir / self._cache_key(input_raw)
        try:
            path.write_text(json.dumps(asdict(result)), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to write enrichment cache: %s", exc)

    def _fallback_result(
        self,
        input_raw: str,
        vendor_hint: str,
        model_hint: str,
        version_hint: str,
        reference_rules: Optional[List],
    ) -> AIEnrichmentResult:
        if self.fallback_func:
            result = self.fallback_func(
                input_raw,
                vendor_hint,
                model_hint,
                version_hint,
                reference_rules,
            )
            if result.ai_source in {"", "AGENT_VENDOR_MODEL"}:
                result.ai_source = "DETERMINISTIC_AGENT"
            return result

        return AIEnrichmentResult(
            ai_vendor_hint=vendor_hint,
            ai_model_hint=model_hint,
            ai_confidence=0.0,
            ai_reason="NO_FALLBACK_CONFIGURED",
            ai_source="DETERMINISTIC_AGENT",
        )

    def enrich(
        self,
        input_raw: str,
        vendor_hint: str,
        model_hint: str,
        version_hint: str,
        reference_rules: Optional[List] = None,
    ) -> AIEnrichmentResult:
        cached = self._load_cache(input_raw)
        if cached:
            return cached

        result = self._fallback_result(
            input_raw,
            vendor_hint,
            model_hint,
            version_hint,
            reference_rules,
        )
        self._save_cache(input_raw, result)
        return result
