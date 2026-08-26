FROM agenthive-backend-dev:0.3.0-alpha.3

# Pin transformers<5.0: FlagEmbedding 1.4.x uses tokenizer.prepare_for_model
# which was removed in transformers 5.x. Use 4.46.x (last compatible 4.x).
RUN pip install --no-cache-dir "FlagEmbedding>=1.3.0" "transformers>=4.44,<5.0"

COPY server.py /app/reranker-server.py

ENV HF_HOME=/data/models
ENV TRANSFORMERS_CACHE=/data/models
ENV MODELSCOPE_CACHE=/data/models
ENV HF_ENDPOINT=https://hf-mirror.com
ENV RERANKER_DEVICE=cpu
ENV RERANKER_USE_FP16=false

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=600s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

WORKDIR /app
CMD ["uvicorn", "reranker-server:app", "--host", "0.0.0.0", "--port", "8000"]
