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


class LiteLLMAdapter(BaseLLMAdapter):
    adapter_name = "litellm"

    async def chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> LLMResponse:
        if self._should_call_live():
            return await self._live_chat(request, context)
        if not llm_mock_allowed():
            raise RuntimeError(llm_mock_disabled_message("LiteLLM adapter"))
        deployment = self.deployment
        model_key = deployment.model_key if deployment else request.model_key or "mock-model"
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
            content="LiteLLM adapter mock response. Configure LiteLLM to enable live calls.",
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
            model_key = deployment.model_key if deployment else request.model_key or "gpt-4o-mini"
            async for delta in self._stream_chat_completions(
                model=model_key,
                messages=[message.model_dump(exclude_none=True) for message in request.messages],
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                timeout_seconds=60,
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
        provider_key = request.provider_key or self.provider.provider_key
        if self._should_call_live():
            try:
                await self._post_chat_completions(
                    model=request.model_key
                    or (self.deployment.model_key if self.deployment else "gpt-4o-mini"),
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    timeout_seconds=request.timeout_seconds,
                )
                latency_ms = int((perf_counter() - started) * 1000)
                return ConnectionTestResult(
                    ok=True,
                    provider_key=provider_key,
                    adapter_type=self.provider.adapter_type,
                    model_key=request.model_key
                    or (self.deployment.model_key if self.deployment else None),
                    latency_ms=latency_ms,
                    message="LiteLLM proxy responded to a live chat completions probe.",
                    diagnostics={
                        "base_url": self._base_url(),
                        "live_network_call": True,
                    },
                )
            except httpx.HTTPError as exc:
                latency_ms = int((perf_counter() - started) * 1000)
                return ConnectionTestResult(
                    ok=False,
                    provider_key=provider_key,
                    adapter_type=self.provider.adapter_type,
                    model_key=request.model_key
                    or (self.deployment.model_key if self.deployment else None),
                    latency_ms=latency_ms,
                    message=f"LiteLLM proxy probe failed: {exc}",
                    diagnostics={
                        "base_url": self._base_url(),
                        "live_network_call": True,
                        "error_type": exc.__class__.__name__,
                    },
                )
        latency_ms = int((perf_counter() - started) * 1000)
        if not llm_mock_allowed():
            return ConnectionTestResult(
                ok=False,
                provider_key=provider_key,
                adapter_type=self.provider.adapter_type,
                model_key=request.model_key
                or (self.deployment.model_key if self.deployment else None),
                latency_ms=latency_ms,
                message=llm_mock_disabled_message("LiteLLM adapter"),
                diagnostics={
                    "base_url": request.base_url
                    or self.provider.base_url
                    or settings.litellm_base_url,
                    "live_network_call": False,
                    "mock_allowed": False,
                    "environment": settings.environment,
                },
            )
        return ConnectionTestResult(
            ok=True,
            provider_key=provider_key,
            adapter_type=self.provider.adapter_type,
            model_key=request.model_key or (self.deployment.model_key if self.deployment else None),
            latency_ms=latency_ms,
            message="LiteLLM adapter configuration accepted in mock mode.",
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
        model_key = deployment.model_key if deployment else request.model_key or "gpt-4o-mini"
        payload = await self._post_chat_completions(
            model=model_key,
            messages=[message.model_dump(exclude_none=True) for message in request.messages],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            timeout_seconds=60,
        )
        content = _extract_content(payload)
        raw_usage = payload.get("usage")
        usage_payload: dict[str, object] = dict(raw_usage) if isinstance(raw_usage, dict) else {}
        input_tokens = _token_count(
            usage_payload.get("prompt_tokens") or usage_payload.get("input_tokens") or 0
        )
        output_tokens = _token_count(
            usage_payload.get("completion_tokens") or usage_payload.get("output_tokens") or 0
        )
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
            finish_reason=_extract_finish_reason(payload),
            metadata={
                "adapter": self.adapter_name,
                "mock": False,
                "live_network_call": True,
                "response_id": payload.get("id"),
            },
        )

    async def _post_chat_completions(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int | None,
        temperature: float | None = None,
        timeout_seconds: float,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {"Authorization": f"Bearer {self._api_key()}"}
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url().rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("LiteLLM proxy returned a non-object response.")
        return data

    async def _stream_chat_completions(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int | None,
        temperature: float | None = None,
        timeout_seconds: float,
    ) -> AsyncIterator[str]:
        """Stream chat completions from the LiteLLM proxy via SSE."""
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {"Authorization": f"Bearer {self._api_key()}"}
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            async with client.stream(
                "POST",
                f"{self._base_url().rstrip('/')}/chat/completions",
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

    def _should_call_live(self) -> bool:
        return bool(
            self.provider.base_url
            and self._api_key()
            and not (self.deployment and self.deployment.config.get("mock") is True)
        )

    def _base_url(self) -> str:
        return self.provider.base_url or settings.litellm_base_url

    def _api_key(self) -> str:
        secret = self.provider.metadata.get("api_key")
        return str(secret) if secret else settings.litellm_master_key


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


def _token_count(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (str, bytes, bytearray, int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0
