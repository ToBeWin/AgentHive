FROM agenthive-backend-dev:0.3.0-alpha.1

# Install sentence-transformers (pulls torch CPU + transformers)
RUN pip install --no-cache-dir "sentence-transformers>=3.0.0"

COPY server.py /app/embedding-server.py

ENV HF_HOME=/data/models
ENV TRANSFORMERS_CACHE=/data/models
ENV MODELSCOPE_CACHE=/data/models
ENV HF_ENDPOINT=https://hf-mirror.com
ENV BGE_DEVICE=cpu
ENV BGE_NORMALIZE=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=600s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

WORKDIR /app
CMD ["uvicorn", "embedding-server:app", "--host", "0.0.0.0", "--port", "8000"]
