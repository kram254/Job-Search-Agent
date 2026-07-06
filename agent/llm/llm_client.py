import os
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("llm_client")


class LLMClient:

    ANTHROPIC_MODEL      = os.environ.get("ANTHROPIC_MODEL",      "claude-opus-4-5")
    GEMINI_MODEL         = os.environ.get("GEMINI_MODEL",         "gemini-1.5-flash")
    GEMINI_VISION_MODEL  = os.environ.get("GEMINI_VISION_MODEL",  "gemini-1.5-flash")
    OPENROUTER_MODEL     = os.environ.get("OPENROUTER_MODEL",     "meta-llama/llama-3.3-70b-instruct:free")
    OLLAMA_MODEL         = os.environ.get("OLLAMA_MODEL",         "nous-hermes2")
    HERMES_OR_MODEL      = "meta-llama/llama-3.3-70b-instruct"
    HERMES_OLLAMA_MODEL  = "nous-hermes2"
    OPENROUTER_BASE      = "https://openrouter.ai"
    COMPOSIO_BASE        = "https://backend.composio.dev"

    STEP_PROVIDERS: Dict[str, str] = {
        "evaluator":  "anthropic",
        "ingestor":   "anthropic",
        "actuator":   "anthropic",
        "generator":  "anthropic",
        "scout":      "gemini",
        "query_gen":  "gemini",
        "hermes":     "hermes",
        "local":      "ollama",
    }

    def __init__(
        self,
        anthropic_api_key:  Optional[str] = None,
        gemini_api_key:     Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        ollama_base_url:    Optional[str] = None,
    ):
        self.anthropic_api_key  = anthropic_api_key  or os.environ.get("ANTHROPIC_API_KEY",  "")
        self.gemini_api_key     = gemini_api_key     or os.environ.get("GEMINI_API_KEY",     "")
        self.openrouter_api_key = openrouter_api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.ollama_base_url    = ollama_base_url    or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self._default_provider  = os.environ.get("LLM_PROVIDER", "").lower().strip()

        self._anthropic_client  = None
        self._anthropic_available  = bool(self.anthropic_api_key)
        self._gemini_available  = bool(self.gemini_api_key)
        self._openrouter_available = bool(self.openrouter_api_key)
        self._ollama_available  = self._probe_ollama()

    def _probe_ollama(self) -> bool:
        try:
            import requests as _r
            resp = _r.get(f"{self.ollama_base_url}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def _get_anthropic_client(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        return self._anthropic_client

    def _resolve_provider(self, step: str = "") -> str:
        if self._default_provider:
            return self._default_provider
        return self.STEP_PROVIDERS.get(step, "anthropic")

    def complete(self, prompt: str, system: str = "",
                 max_tokens: int = 1024, temperature: float = 0.3) -> str:
        provider = self._resolve_provider()
        return self._dispatch(provider, prompt, system, max_tokens, temperature)

    def complete_for_step(self, step: str, prompt: str, system: str = "",
                          max_tokens: int = 1024, temperature: float = 0.3) -> str:
        provider = self._resolve_provider(step)
        return self._dispatch(provider, prompt, system, max_tokens, temperature, step=step)

    def complete_with_provider(self, provider: str, prompt: str, system: str = "",
                               max_tokens: int = 1024, temperature: float = 0.3,
                               model: Optional[str] = None) -> str:
        return self._dispatch(provider, prompt, system, max_tokens, temperature, model=model)

    def _dispatch(self, provider: str, prompt: str, system: str,
                  max_tokens: int, temperature: float,
                  step: str = "", model: Optional[str] = None) -> str:
        if provider == "openrouter":
            return self._openrouter_complete(prompt, system, max_tokens, temperature, model=model)
        if provider == "ollama":
            return self._ollama_complete(prompt, system, max_tokens, temperature, model=model)
        if provider == "hermes":
            return self._hermes_complete(prompt, system, max_tokens, temperature)
        if provider == "gemini":
            if self._gemini_available:
                try:
                    return self._gemini_complete(prompt, system, max_tokens, temperature)
                except Exception as e:
                    logger.warning(f"Gemini failed for step '{step}', falling back: {e}")
            if self._anthropic_available:
                return self._anthropic_complete(prompt, system, max_tokens, temperature)
            if self._openrouter_available:
                return self._openrouter_complete(prompt, system, max_tokens, temperature)
            return self._anthropic_complete(prompt, system, max_tokens, temperature)
        if not self._anthropic_available and self._openrouter_available:
            logger.info("ANTHROPIC_API_KEY not set — routing to OpenRouter")
            return self._openrouter_complete(prompt, system, max_tokens, temperature)
        try:
            return self._anthropic_complete(prompt, system, max_tokens, temperature)
        except Exception as e:
            err = str(e).lower()
            if any(kw in err for kw in ("quota", "rate_limit", "overloaded", "529", "authentication", "invalid_api_key")):
                logger.warning(f"Anthropic error, trying fallback: {e}")
                if self._openrouter_available:
                    return self._openrouter_complete(prompt, system, max_tokens, temperature)
                if self._gemini_available:
                    return self._gemini_complete(prompt, system, max_tokens, temperature)
                if self._ollama_available:
                    return self._ollama_complete(prompt, system, max_tokens, temperature)
            raise

    def _anthropic_complete(self, prompt: str, system: str,
                             max_tokens: int, temperature: float) -> str:
        client = self._get_anthropic_client()
        messages = [{"role": "user", "content": prompt}]
        kwargs: Dict[str, Any] = {
            "model": self.ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "messages": messages,
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
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        return candidates[0]["content"]["parts"][0]["text"]

    def _openrouter_complete(self, prompt: str, system: str,
                              max_tokens: int, temperature: float,
                              model: Optional[str] = None) -> str:
        import requests
        if not self.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model":       model or self.OPENROUTER_MODEL,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
            "stream":      False,
        }
        headers = {
            "Authorization":    f"Bearer {self.openrouter_api_key}",
            "Content-Type":     "application/json",
            "HTTP-Referer":     "https://github.com/kram254/Job-Search-Agent",
            "X-OpenRouter-Title": "Job-Search-Agent",
        }
        resp = requests.post(
            f"{self.OPENROUTER_BASE}/api/v1/chat/completions",
            json=payload, headers=headers, timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices: {data}")
        return choices[0]["message"]["content"]

    def _ollama_complete(self, prompt: str, system: str,
                         max_tokens: int, temperature: float,
                         model: Optional[str] = None) -> str:
        import requests
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model":   model or self.OLLAMA_MODEL,
            "messages": messages,
            "stream":  False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        resp = requests.post(
            f"{self.ollama_base_url}/api/chat",
            json=payload, timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    def _hermes_complete(self, prompt: str, system: str,
                          max_tokens: int, temperature: float) -> str:
        if self._openrouter_available:
            return self._openrouter_complete(
                prompt, system, max_tokens, temperature, model=self.HERMES_OR_MODEL,
            )
        if self._ollama_available:
            return self._ollama_complete(
                prompt, system, max_tokens, temperature, model=self.HERMES_OLLAMA_MODEL,
            )
        raise RuntimeError(
            "Hermes provider unavailable. Set OPENROUTER_API_KEY or start Ollama with 'ollama pull nous-hermes2'."
        )

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

    def complete_vision(self, img_b64: str, prompt: str, system: str = "",
                        max_tokens: int = 512) -> str:
        if self._gemini_available:
            try:
                return self._gemini_vision_complete(img_b64, prompt, system, max_tokens)
            except Exception as e:
                logger.warning(f"Gemini vision failed, falling back to Anthropic: {e}")
        return self._anthropic_vision_complete(img_b64, prompt, system, max_tokens)

    def _gemini_vision_complete(self, img_b64: str, prompt: str,
                                 system: str, max_tokens: int) -> str:
        import requests
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.GEMINI_VISION_MODEL}:generateContent?key={self.gemini_api_key}"
        )
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        payload = {
            "contents": [{"parts": [
                {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                {"text": full_prompt},
            ]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.0},
        }
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini vision returned no candidates")
        return candidates[0]["content"]["parts"][0]["text"]

    def _anthropic_vision_complete(self, img_b64: str, prompt: str,
                                    system: str, max_tokens: int) -> str:
        client = self._get_anthropic_client()
        content: List[Any] = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
            {"type": "text", "text": prompt},
        ]
        kwargs: Dict[str, Any] = {
            "model":    self.ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}],
        }
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)
        return response.content[0].text

    def list_openrouter_models(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        import requests
        if not self.openrouter_api_key:
            return []
        try:
            resp = requests.get(
                f"{self.OPENROUTER_BASE}/api/v1/models",
                headers={"Authorization": f"Bearer {self.openrouter_api_key}"},
                timeout=15,
            )
            resp.raise_for_status()
            models = resp.json().get("data", [])
            if category:
                models = [m for m in models if category.lower() in m.get("id", "").lower()]
            return models
        except Exception as e:
            logger.error(f"list_openrouter_models failed: {e}")
            return []

    def list_ollama_models(self) -> List[str]:
        import requests
        try:
            resp = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    def provider_status(self) -> Dict[str, Any]:
        active = (
            "openrouter" if not self._anthropic_available and self._openrouter_available
            else self._default_provider or "anthropic (step-based routing)"
        )
        return {
            "anthropic":   {"available": self._anthropic_available, "model": self.ANTHROPIC_MODEL},
            "gemini":      {"available": self._gemini_available,    "model": self.GEMINI_MODEL},
            "openrouter":  {"available": self._openrouter_available, "model": self.OPENROUTER_MODEL},
            "ollama":      {"available": self._ollama_available,    "model": self.OLLAMA_MODEL,
                            "base_url": self.ollama_base_url},
            "hermes":      {"available": self._openrouter_available or self._ollama_available,
                            "routes_to": "openrouter" if self._openrouter_available else "ollama"},
            "active_provider": active,
        }

    def provider(self) -> str:
        return self._default_provider or "anthropic"

    def is_gemini_available(self) -> bool:
        return self._gemini_available
