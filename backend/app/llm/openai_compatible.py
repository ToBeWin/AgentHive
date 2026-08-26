from collections.abc import AsyncIterator
import json
from time import perf_counter

import httpx

from app.core.config import settings
from app.llm.base import BaseLLMAdapter
from app.llm.mock_policy import llm_mock_allowed, llm_mock_disabled_message
from app.llm.pricing import ModelPricingCatalog
from app.llm.schemas import (
    ConnectionTestRequest,
    ConnectionTestResult,
    LLMChatRequest,
    LLMRequestContext,
    LLMResponse,
)

# Maps local inference engine provider_key to its optional api_key setting attr.
_LOCAL_ENGINE_API_KEY_ATTRS: dict[str, str] = {
    "ollama": "ollama_api_key",
    "vllm": "vllm_api_key",
    "sglang": "sglang_api_key",
    "lmstudio": "lmstudio_api_key",
    "xinference": "xinference_api_key",
    "localai": "localai_api_key",
}

# Maps local inference engine provider_key to its base_url setting attr.
_LOCAL_ENGINE_BASE_URL_ATTRS: dict[str, str] = {
    "ollama": "ollama_base_url",
    "vllm": "vllm_base_url",
    "sglang": "sglang_base_url",
    "lmstudio": "lmstudio_base_url",
    "xinference": "xinference_base_url",
    "localai": "localai_base_url",
}


def _local_engine_base_url(provider_key: str) -> str | None:
    attr = _LOCAL_ENGINE_BASE_URL_ATTRS.get(provider_key)
    if attr is None:
        return None
    return getattr(settings, attr) or None


def _local_engine_api_key(provider_key: str) -> str:
    attr = _LOCAL_ENGINE_API_KEY_ATTRS.get(provider_key)
    if attr is None:
        return ""
    return str(getattr(settings, attr) or "")


class OpenAICompatibleAdapter(BaseLLMAdapter):
    adapter_name = "openai_compatible"
    reasoning_model_min_output_tokens = 512

    async def chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> LLMResponse:
        if self._should_call_live():
            return await self._live_chat(request, context)
        if not llm_mock_allowed():
            raise RuntimeError(llm_mock_disabled_message("OpenAI-compatible adapter"))
        deployment = self.deployment
        model_key = deployment.model_key if deployment else request.model_key or "openai-compatible"
        usage = ModelPricingCatalog().calculate(
            input_tokens=sum(max(1, len(message.content) // 4) for message in request.messages),
            output_tokens=min(request.max_tokens or 128, 128),
            model_key=model_key,
        )
        return LLMResponse(
            request_id=context.request_id,
            model_key=model_key,
            provider_key=self.provider.provider_key,
            deployment_id=deployment.id if deployment else None,
            content=(
                "OpenAI-compatible adapter mock response. Configure endpoint credentials "
                "to enable live calls."
            ),
            usage=usage,
            finish_reason="stop",
            metadata={"adapter": self.adapter_name, "mock": True},
        )

    async def stream_chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> AsyncIterator[str]:
        if self._should_call_live():
            deployment = self.deployment
            model_key = deployment.model_key if deployment else request.model_key or "local-chat"
            messages = [message.model_dump(exclude_none=True) for message in request.messages]
            async for delta in self._stream_chat_completions(
                model=model_key,
                messages=messages,
                max_tokens=_effective_max_tokens(
                    model_key=model_key,
                    provider_key=self.provider.provider_key,
                    requested_max_tokens=request.max_tokens,
                ),
                temperature=request.temperature,
                timeout_seconds=60,
                api_key=self._api_key(),
                base_url=self._base_url() or "",
            ):
                yield delta
            return
        # Mock fallback: stream the mock response word-by-word so dev mode
        # still exercises the streaming transport.
        response = await self.chat(request, context)
        for chunk in response.content.split(" "):
            yield f"{chunk} "

    async def test_connection(
        self,
        request: ConnectionTestRequest,
    ) -> ConnectionTestResult:
        started = perf_counter()
        if self._should_call_live(request):
            try:
                await self._post_chat_completions(
                    model=request.model_key
                    or (self.deployment.model_key if self.deployment else "local-chat"),
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    timeout_seconds=request.timeout_seconds,
                    api_key=request.api_key or self._api_key(),
                    base_url=request.base_url or self._base_url(),
                )
                latency_ms = int((perf_counter() - started) * 1000)
                return ConnectionTestResult(
                    ok=True,
                    provider_key=request.provider_key or self.provider.provider_key,
                    adapter_type=self.provider.adapter_type,
                    model_key=request.model_key
                    or (self.deployment.model_key if self.deployment else None),
                    latency_ms=latency_ms,
                    message="OpenAI-compatible endpoint responded to a live chat completions probe.",
                    diagnostics={
                        "base_url": request.base_url or self._base_url(),
                        "live_network_call": True,
                    },
                )
            except httpx.HTTPError as exc:
                latency_ms = int((perf_counter() - started) * 1000)
                return ConnectionTestResult(
                    ok=False,
                    provider_key=request.provider_key or self.provider.provider_key,
                    adapter_type=self.provider.adapter_type,
                    model_key=request.model_key
                    or (self.deployment.model_key if self.deployment else None),
                    latency_ms=latency_ms,
                    message=f"OpenAI-compatible endpoint probe failed: {exc}",
                    diagnostics={
                        "base_url": request.base_url or self._base_url(),
                        "live_network_call": True,
                        "error_type": exc.__class__.__name__,
                    },
                )
        latency_ms = int((perf_counter() - started) * 1000)
        if not llm_mock_allowed():
            return ConnectionTestResult(
                ok=False,
                provider_key=request.provider_key or self.provider.provider_key,
                adapter_type=self.provider.adapter_type,
                model_key=request.model_key
                or (self.deployment.model_key if self.deployment else None),
                latency_ms=latency_ms,
                message=llm_mock_disabled_message("OpenAI-compatible adapter"),
                diagnostics={
                    "base_url": request.base_url
                    or self.provider.base_url
                    or settings.openai_compatible_base_url,
                    "live_network_call": False,
                    "mock_allowed": False,
                    "environment": settings.environment,
                },
            )
        return ConnectionTestResult(
            ok=True,
            provider_key=request.provider_key or self.provider.provider_key,
            adapter_type=self.provider.adapter_type,
            model_key=request.model_key or (self.deployment.model_key if self.deployment else None),
            latency_ms=latency_ms,
            message="OpenAI-compatible endpoint configuration accepted in mock mode.",
            diagnostics={
                "base_url": request.base_url or self.provider.base_url,
                "live_network_call": False,
                "mock_allowed": True,
            },
        )

    async def _live_chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> LLMResponse:
        deployment = self.deployment
        model_key = deployment.model_key if deployment else request.model_key or "local-chat"
        payload = await self._post_chat_completions(
            model=model_key,
            messages=[message.model_dump(exclude_none=True) for message in request.messages],
            max_tokens=_effective_max_tokens(
                model_key=model_key,
                provider_key=self.provider.provider_key,
                requested_max_tokens=request.max_tokens,
            ),
            temperature=request.temperature,
            timeout_seconds=60,
            api_key=self._api_key(),
            base_url=self._base_url(),
        )
        content = _extract_content(payload)
        finish_reason = _extract_finish_reason(payload)
        raw_usage = payload.get("usage")
        usage_payload: dict[str, object] = dict(raw_usage) if isinstance(raw_usage, dict) else {}
        input_tokens = _token_count(
            usage_payload.get("prompt_tokens") or usage_payload.get("input_tokens") or 0
        )
        output_tokens = _token_count(
            usage_payload.get("completion_tokens") or usage_payload.get("output_tokens") or 0
        )
        reasoning_tokens = _extract_reasoning_tokens(usage_payload)
        usage = ModelPricingCatalog().calculate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_key=model_key,
        )
        return LLMResponse(
            request_id=context.request_id,
            model_key=model_key,
            provider_key=self.provider.provider_key,
            deployment_id=deployment.id if deployment else None,
            content=content,
            usage=usage,
            finish_reason=finish_reason,
            metadata={
                "adapter": self.adapter_name,
                "mock": False,
                "live_network_call": True,
                "response_id": payload.get("id"),
                "empty_content_reason": _empty_content_reason(
                    content=content,
                    finish_reason=finish_reason,
                    reasoning_tokens=reasoning_tokens,
                ),
                "reasoning_tokens": reasoning_tokens,
            },
        )

    async def _post_chat_completions(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int | None,
        timeout_seconds: float,
        api_key: str,
        base_url: str | None,
        temperature: float | None = None,
    ) -> dict[str, object]:
        if not base_url:
            raise ValueError("OpenAI-compatible base_url is required for live calls.")
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("OpenAI-compatible endpoint returned a non-object response.")
        return data

    async def _stream_chat_completions(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int | None,
        timeout_seconds: float,
        api_key: str,
        base_url: str,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completions via SSE, yielding content deltas."""
        if not base_url:
            raise ValueError("OpenAI-compatible base_url is required for live streaming.")
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            async with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield content

    def _should_call_live(self, request: ConnectionTestRequest | None = None) -> bool:
        base_url = request.base_url if request else None
        api_key = request.api_key if request else None
        has_target = bool(base_url or self._base_url())
        has_secret = bool(api_key or self._api_key())
        is_mock = self.deployment and self.deployment.config.get("mock") is True
        # Local inference engines (Ollama/vLLM/...) typically run without auth
        # on localhost; base_url alone is sufficient for a live call.
        auth_required = self.provider.metadata.get("auth_required", True) is not False
        if has_target and not is_mock and not auth_required:
            return True
        return has_target and has_secret and not is_mock

    def _base_url(self) -> str | None:
        if self.provider.base_url:
            return self.provider.base_url
        # Local inference engine base_url (Ollama/vLLM/...) takes precedence
        # over the generic openai_compatible fallback.
        engine_url = _local_engine_base_url(self.provider.provider_key)
        if engine_url:
            return engine_url
        return settings.openai_compatible_base_url

    def _api_key(self) -> str:
        secret = self.provider.metadata.get("api_key")
        if secret:
            return str(secret)
        # Per-engine API key for local inference providers (optional auth).
        engine_key = _local_engine_api_key(self.provider.provider_key)
        if engine_key:
            return engine_key
        return settings.openai_compatible_api_key


def _extract_content(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return str(message["content"])
            if isinstance(first.get("text"), str):
                return str(first["text"])
    return ""


def _extract_finish_reason(payload: dict[str, object]) -> str | None:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        finish_reason = choices[0].get("finish_reason")
        return finish_reason if isinstance(finish_reason, str) else None
    return None


def _effective_max_tokens(
    *,
    model_key: str,
    provider_key: str,
    requested_max_tokens: int | None,
) -> int | None:
    if not _is_reasoning_heavy_model(model_key=model_key, provider_key=provider_key):
        return requested_max_tokens
    if requested_max_tokens is None:
        return OpenAICompatibleAdapter.reasoning_model_min_output_tokens
    return max(requested_max_tokens, OpenAICompatibleAdapter.reasoning_model_min_output_tokens)


def _is_reasoning_heavy_model(*, model_key: str, provider_key: str) -> bool:
    normalized_model = model_key.lower()
    normalized_provider = provider_key.lower()
    return normalized_provider == "mimo" or normalized_model.startswith("mimo-")


def _extract_reasoning_tokens(usage_payload: dict[str, object]) -> int | None:
    details = usage_payload.get("completion_tokens_details")
    if not isinstance(details, dict):
        return None
    value = details.get("reasoning_tokens")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _token_count(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (str, bytes, bytearray, int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _empty_content_reason(
    *,
    content: str,
    finish_reason: str | None,
    reasoning_tokens: int | None,
) -> str | None:
    if content:
        return None
    if finish_reason == "length" and reasoning_tokens:
        return "reasoning_tokens_exhausted_output_budget"
    if finish_reason == "length":
        return "output_budget_exhausted"
    return "provider_returned_empty_content"
