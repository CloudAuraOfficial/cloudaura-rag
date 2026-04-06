FROM python:3.12-slim AS builder

WORKDIR /build
COPY p4-autonomous/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY shared/ shared/
COPY p4-autonomous/app/ app/
COPY corpus/ corpus/

ENV PYTHONPATH=/app/shared
ENV TRANSFORMERS_CACHE=/app/model_cache
ENV SENTENCE_TRANSFORMERS_HOME=/app/model_cache
ENV HF_HOME=/app/model_cache

RUN mkdir -p /app/chroma_data /app/model_cache && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8014

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8014/health', timeout=5).raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8014"]
