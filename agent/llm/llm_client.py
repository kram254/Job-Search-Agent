import os
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("llm_client")


class LLMClient:

    ANTHROPIC_MODEL = "claude-opus-4-5"
    GEMINI_MODEL = "gemini-1.5-flash"

    STEP_PROVIDERS: Dict[str, str] = {
        "evaluator":  "anthropic",
        "ingestor":   "anthropic",
        "actuator":   "anthropic",
        "generator":  "anthropic",
        "scout":      "gemini",
        "query_gen":  "gemini",
    }

    def __init__(self, anthropic_api_key: Optional[str] = None,
                 gemini_api_key: Optional[str] = None):
        self.anthropic_api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self._provider = "anthropic"
        self._anthropic_client = None
        self._gemini_available = bool(self.gemini_api_key)

    def _get_anthropic_client(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        return self._anthropic_client

    def complete(self, prompt: str, system: str = "",
                 max_tokens: int = 1024, temperature: float = 0.3) -> str:
        try:
            return self._anthropic_complete(prompt, system, max_tokens, temperature)
        except Exception as e:
            error_str = str(e).lower()
            if any(kw in error_str for kw in ("quota", "rate_limit", "overloaded", "529", "529")):
                logger.warning(f"Anthropic quota/rate error, falling back to Gemini: {e}")
                if self._gemini_available:
                    return self._gemini_complete(prompt, system, max_tokens, temperature)
            raise

    def _anthropic_complete(self, prompt: str, system: str,
                             max_tokens: int, temperature: float) -> str:
        client = self._get_anthropic_client()
        messages = [{"role": "user", "content": prompt}]
        kwargs: Dict[str, Any] = {
            "model": self.ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "messages": messages
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        return response.content[0].text

    def _gemini_complete(self, prompt: str, system: str,
                         max_tokens: int, temperature: float) -> str:
        import requests
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.GEMINI_MODEL}:generateContent?key={self.gemini_api_key}"
        )
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
            }
        }
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        return candidates[0]["content"]["parts"][0]["text"]

    def complete_for_step(self, step: str, prompt: str, system: str = "",
                          max_tokens: int = 1024, temperature: float = 0.3) -> str:
        preferred = self.STEP_PROVIDERS.get(step, "anthropic")
        if preferred == "gemini" and self._gemini_available:
            try:
                return self._gemini_complete(prompt, system, max_tokens, temperature)
            except Exception as e:
                logger.warning(f"Gemini failed for step '{step}', falling back to Anthropic: {e}")
                return self._anthropic_complete(prompt, system, max_tokens, temperature)
        return self.complete(prompt, system=system, max_tokens=max_tokens, temperature=temperature)

    def complete_json(self, prompt: str, system: str = "",
                      max_tokens: int = 1024) -> Any:
        raw = self.complete(prompt, system=system, max_tokens=max_tokens)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}

    def provider(self) -> str:
        return self._provider

    def is_gemini_available(self) -> bool:
        return self._gemini_available
