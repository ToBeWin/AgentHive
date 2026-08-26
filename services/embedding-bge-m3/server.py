"""OpenAI-compatible BGE-M3 embedding service.

Provides /v1/embeddings and /embeddings endpoints that accept the same request
shape as OpenAI's embeddings API, so AgentHive's LLMGatewayEmbeddingAdapter can
call it directly.

BGE-M3 outputs 1024-dimensional dense vectors and supports 100+ languages
(including Chinese), making it suitable for the customer-service RAG scenario.
"""

from __future__ import annotations

import os
import time
from typing import Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

MODEL_NAME = os.environ.get("BGE_MODEL_NAME", "BAAI/bge-m3")
DEVICE = os.environ.get("BGE_DEVICE", "cpu")
NORMALIZE = os.environ.get("BGE_NORMALIZE", "true").lower() == "true"

# Prefer ModelScope cache layout (/data/models/BAAI/bge-m3).
# Fall back to HuggingFace mirror only if the local snapshot is missing.
_model_cache_root = os.environ.get("MODELSCOPE_CACHE") or os.environ.get("HF_HOME") or "/data/models"
_local_model_dir = os.path.join(_model_cache_root, MODEL_NAME)
if os.path.isdir(_local_model_dir) and os.listdir(_local_model_dir):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    _load_target = _local_model_dir
    print(f"[bge-m3] Using local snapshot at {_load_target}", flush=True)
else:
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    _load_target = MODEL_NAME
    print(f"[bge-m3] No local snapshot, will download from HF mirror", flush=True)

from sentence_transformers import SentenceTransformer  # noqa: E402

print(f"[bge-m3] Loading model {_load_target} on device={DEVICE} ...", flush=True)
_load_start = time.monotonic()
_model = SentenceTransformer(_load_target, device=DEVICE)
_load_seconds = time.monotonic() - _load_start
_dim = _model.get_sentence_embedding_dimension()
print(f"[bge-m3] Model loaded in {_load_seconds:.1f}s, dimensions={_dim}", flush=True)

app = FastAPI(title="BGE-M3 Embedding Service", version="1.0.0")


class EmbeddingRequest(BaseModel):
    input: Union[str, list[str]]
    model: str = "bge-m3"
    encoding_format: str = "float"


class EmbeddingData(BaseModel):
    object: str = "embedding"
    embedding: list[float]
    index: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingData]
    model: str
    usage: dict[str, int]


@app.post("/v1/embeddings")
@app.post("/embeddings")
async def create_embeddings(req: EmbeddingRequest) -> EmbeddingResponse:
    if not req.input:
        raise HTTPException(status_code=400, detail="input is required")
    texts = [req.input] if isinstance(req.input, str) else list(req.input)
    if len(texts) > 64:
        raise HTTPException(status_code=400, detail="too many inputs (max 64 per request)")

    embeddings = _model.encode(
        texts,
        normalize_embeddings=NORMALIZE,
        batch_size=min(len(texts), 32),
        show_progress_bar=False,
    )

    data = [
        EmbeddingData(embedding=emb.tolist(), index=i)
        for i, emb in enumerate(embeddings)
    ]
    total_chars = sum(len(t) for t in texts)
    return EmbeddingResponse(
        data=data,
        model=req.model,
        usage={
            "prompt_tokens": total_chars,
            "total_tokens": total_chars,
        },
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "dimensions": _dim,
        "device": DEVICE,
    }


@app.get("/")
async def root():
    return {
        "service": "bge-m3-embedding",
        "model": MODEL_NAME,
        "dimensions": _dim,
        "endpoints": ["/v1/embeddings", "/embeddings", "/health"],
    }
