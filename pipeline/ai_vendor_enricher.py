"""
AI-powered vendor/model enrichment with deterministic fallback and audit controls.

This module integrates with GitHub Copilot (via Azure OpenAI endpoints) to enrich 
hardware model strings. All results are supplemental and logged for auditability.

Determinism is ensured via:
- Consistent prompts
- Fixed seed/temperature
- Result caching
- Explicit fallback chain

Audit trails include:
- ai_confidence: score from 0.0 to 1.0
- ai_reason: WHY the AI made this decision
- ai_source: WHERE the result came from (LLM_COPILOT, DETERMINISTIC_FALLBACK, CACHE, etc.)
- ai_vendor_hint, ai_model_hint: the enriched values
"""

import json
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class AIEnrichmentResult:
    """Result from AI enrichment. All fields are supplemental and non-authoritative."""
    ai_vendor_hint: str
    ai_model_hint: str
    ai_confidence: float
    ai_reason: str
    ai_source: str


class AIVendorEnricher:
    """
    LLM-powered vendor/model enrichment with deterministic fallback and caching.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        cache_dir: Optional[Path] = None,
        enable_cache: bool = True,
        fallback_func=None,
    ):
        """
        Args:
            api_key: GitHub Copilot / Azure OpenAI API key (if None, uses fallback only)
            model: Model identifier (e.g., 'gpt-4', deployment name)
            cache_dir: Directory to store result cache
            enable_cache: Whether to cache results
            fallback_func: Callable(input_raw, vendor_hint, model_hint, version_hint, reference_rules) -> AIEnrichmentResult
        """
        self.api_key = api_key
        self.model = model
        self.enable_cache = enable_cache
        self.cache_dir = cache_dir or Path(".cache/ai_vendor_enricher")
        self.fallback_func = fallback_func
        self._cache: Dict[str, AIEnrichmentResult] = {}
        self._llm_client = None

        # Initialize GitHub Copilot (Azure OpenAI) client
        if api_key:
            self._init_copilot_client(api_key)

        if enable_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _init_copilot_client(self, api_key: str) -> None:
        """Initialize GitHub Copilot client (via Azure OpenAI)."""
        try:
            import openai
            openai.api_key = api_key
            self._llm_client = openai
            logger.debug("GitHub Copilot (Azure OpenAI) client initialized")
        except ImportError:
            logger.warning("openai package not installed; using deterministic fallback only")
        except Exception as e:
            logger.warning(f"Failed to initialize Copilot client: {e}")


    def _cache_key(self, input_raw: str) -> str:
        """Generate deterministic cache key."""
        h = hashlib.sha256(input_raw.encode('utf-8')).hexdigest()
        return f"enrichment_{h}.json"

    def _load_cache(self, input_raw: str) -> Optional[AIEnrichmentResult]:
        """Load cached result if available."""
        if not self.enable_cache:
            return None

        cache_file = self.cache_dir / self._cache_key(input_raw)
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text('utf-8'))
                result = AIEnrichmentResult(**data)
                logger.debug(f"Cache hit for: {input_raw[:50]}")
                return result
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        return None

    def _save_cache(self, input_raw: str, result: AIEnrichmentResult) -> None:
        """Save result to cache."""
        if not self.enable_cache:
            return

        try:
            cache_file = self.cache_dir / self._cache_key(input_raw)
            cache_file.write_text(json.dumps(asdict(result)), encoding='utf-8')
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _call_llm(self, prompt: str) -> Tuple[Optional[str], str]:
        """
        Call GitHub Copilot (Azure OpenAI) API with fixed parameters for determinism.
        Returns (response_text, error_reason).
        """
        if not self._llm_client:
            return None, "NO_LLM_CLIENT"

        try:
            response = self._llm_client.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a hardware model parser. Return ONLY valid JSON. "
                            "Do not explain or add commentary. Be deterministic and consistent."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,  # Determinism: no randomness
                max_tokens=500,
                timeout=10,
            )
            text = response.choices[0].message.content.strip()
            return text, ""
        except Exception as e:
            reason = f"LLM_ERROR:{str(e)[:50]}"
            logger.warning(f"Copilot call failed: {reason}")
            return None, reason

    def _parse_llm_response(self, response_text: str) -> Tuple[str, str, float, str]:
        """
        Parse LLM JSON response.
        Returns (vendor_hint, model_hint, confidence, reason).
        """
        try:
            data = json.loads(response_text)
            vendor_hint = str(data.get("vendor_hint", "UNKNOWN")).strip()
            model_hint = str(data.get("model_hint", "UNKNOWN")).strip()
            confidence = float(data.get("confidence", 0.5))
            reason = str(data.get("reason", "PARSE_SUCCESS"))
            confidence = max(0.0, min(1.0, confidence))
            return vendor_hint, model_hint, confidence, reason
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return "UNKNOWN", "UNKNOWN", 0.0, f"PARSE_ERROR:{str(e)[:30]}"

    def _enrich_via_llm(
        self,
        input_raw: str,
        vendor_hint: str,
        model_hint: str,
        version_hint: str,
    ) -> AIEnrichmentResult:
        """Call GitHub Copilot with structured prompt and return enriched result."""
        prompt = (
            f"Parse this hardware model string into structured components.\n\n"
            f"Input: {input_raw}\n"
            f"Current parse:\n"
            f"  vendor: {vendor_hint}\n"
            f"  model: {model_hint}\n"
            f"  version: {version_hint}\n\n"
            f"Respond with JSON:\n"
            f'{{\n'
            f'  "vendor_hint": "vendor name or UNKNOWN",\n'
            f'  "model_hint": "model name or UNKNOWN",\n'
            f'  "confidence": 0.0-1.0,\n'
            f'  "reason": "why this parse"\n'
            f'}}\n\n'
            f"Rules:\n"
            f"- If unsure, return UNKNOWN (do not guess)\n"
            f"- Confidence 0.80+ only if high certainty\n"
            f"- Return ONLY JSON, no explanation"
        )

        response_text, error_reason = self._call_llm(prompt)

        if response_text:
            vendor, model, confidence, reason = self._parse_llm_response(response_text)
            return AIEnrichmentResult(
                ai_vendor_hint=vendor,
                ai_model_hint=model,
                ai_confidence=confidence,
                ai_reason=reason,
                ai_source="LLM_COPILOT",
            )
        else:
            logger.info(f"LLM enrichment failed ({error_reason}), falling back to deterministic")
            return self._enrich_via_fallback(
                input_raw, vendor_hint, model_hint, version_hint, error_reason
            )

    def _enrich_via_fallback(
        self,
        input_raw: str,
        vendor_hint: str,
        model_hint: str,
        version_hint: str,
        context: str = "",
    ) -> AIEnrichmentResult:
        """Fall back to deterministic enrichment."""
        if self.fallback_func:
            result = self.fallback_func(
                input_raw, vendor_hint, model_hint, version_hint, None
            )
            # Update source to indicate this came from fallback
            result.ai_source = f"DETERMINISTIC_FALLBACK({context})" if context else "DETERMINISTIC_FALLBACK"
            return result
        else:
            return AIEnrichmentResult(
                ai_vendor_hint=vendor_hint,
                ai_model_hint=model_hint,
                ai_confidence=0.0,
                ai_reason="NO_FALLBACK_CONFIGURED",
                ai_source="NOOP",
            )

    def enrich(
        self,
        input_raw: str,
        vendor_hint: str,
        model_hint: str,
        version_hint: str,
        reference_rules: Optional[List] = None,
    ) -> AIEnrichmentResult:
        """
        Enrich vendor/model with AI, using cache and fallback as needed.

        Args:
            input_raw: Raw hardware string
            vendor_hint: Current vendor guess
            model_hint: Current model guess
            version_hint: Current version guess
            reference_rules: Optional reference rules (currently unused by LLM)

        Returns:
            AIEnrichmentResult with all audit fields populated.
        """
        # Check cache first
        cached = self._load_cache(input_raw)
        if cached:
            return cached

        # Try LLM
        result = self._enrich_via_llm(
            input_raw, vendor_hint, model_hint, version_hint
        )

        # Save to cache
        self._save_cache(input_raw, result)

        return result
