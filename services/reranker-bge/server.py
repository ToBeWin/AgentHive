"""BGE-Reranker-v2-m3 reranking service.

Provides a /rerank endpoint that accepts a query and a list of candidate
texts, then returns relevance scores using a cross-encoder model.

BGE-Reranker-v2-m3 supports 100+ languages (including Chinese) and is
optimised for RAG scenarios where coarse bi-encoder retrieval (e.g. BGE-M3)
needs to be refined by a more precise cross-encoder pass.
"""

from __future__ import annotations

import os
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Prefer ModelScope cache layout (/data/models/BAAI/bge-reranker-v2-m3).
# Fall back to HuggingFace mirror only if the local snapshot is missing.
MODEL_NAME = os.environ.get("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
DEVICE = os.environ.get("RERANKER_DEVICE", "cpu")
USE_FP16 = os.environ.get("RERANKER_USE_FP16", "false").lower() == "true"

_model_cache_root = os.environ.get("MODELSCOPE_CACHE") or os.environ.get("HF_HOME") or "/data/models"
_local_model_dir = os.path.join(_model_cache_root, MODEL_NAME)
if os.path.isdir(_local_model_dir) and os.listdir(_local_model_dir):
    # Offline mode: skip HuggingFace Hub network calls entirely.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    _load_target = _local_model_dir
    print(f"[reranker] Using local snapshot at {_load_target}", flush=True)
else:
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    _load_target = MODEL_NAME
    print(f"[reranker] No local snapshot, will download from HF mirror", flush=True)

from FlagEmbedding import FlagReranker  # noqa: E402

print(f"[reranker] Loading model {_load_target} on device={DEVICE} ...", flush=True)
_load_start = time.monotonic()
_model = FlagReranker(_load_target, device=DEVICE, use_fp16=USE_FP16)
_load_seconds = time.monotonic() - _load_start
print(f"[reranker] Model loaded in {_load_seconds:.1f}s", flush=True)

app = FastAPI(title="BGE Reranker Service", version="1.0.0")


class RerankRequest(BaseModel):
    query: str
    texts: list[str]
    top_n: int | None = Field(default=None, ge=1)
    raw_scores: bool = False


class RerankResult(BaseModel):
    index: int
    score: float
    text: str | None = None


class RerankResponse(BaseModel):
    results: list[RerankResult]
    model: str


@app.post("/rerank")
@app.post("/v1/rerank")
async def rerank(req: RerankRequest) -> RerankResponse:
    if not req.query:
        raise HTTPException(status_code=400, detail="query is required")
    if not req.texts:
        raise HTTPException(status_code=400, detail="texts is required")
    if len(req.texts) > 64:
        raise HTTPException(status_code=400, detail="too many texts (max 64 per request)")

    pairs = [[req.query, text] for text in req.texts]
    scores = _model.compute_score(pairs, normalize=not req.raw_scores)

    # compute_score returns a list for multi-pair input
    if not isinstance(scores, list):
        scores = [scores]

    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)

    if req.top_n:
        indexed = indexed[: req.top_n]

    results = [
        RerankResult(index=i, score=float(s), text=req.texts[i] if i < len(req.texts) else None)
        for i, s in indexed
    ]
    return RerankResponse(results=results, model=MODEL_NAME)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "device": DEVICE,
    }


@app.get("/")
async def root():
    return {
        "service": "bge-reranker",
        "model": MODEL_NAME,
        "endpoints": ["/rerank", "/v1/rerank", "/health"],
    }
