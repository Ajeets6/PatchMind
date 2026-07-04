FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PATCHMIND_TRANSPORT=streamable-http \
    PATCHMIND_MEMORY_MODE=local \
    PATCHMIND_COGNEE_DATA_DIR=/data/cognee/data \
    PATCHMIND_COGNEE_SYSTEM_DIR=/data/cognee/system \
    COGNEE_SKIP_CONNECTION_TEST=true \
    LLM_PROVIDER=ollama \
    LLM_MODEL=qwen2.5-coder:7b \
    LLM_ENDPOINT=http://host.docker.internal:11434/v1 \
    LLM_API_KEY=ollama \
    LLM_MAX_COMPLETION_TOKENS=4096 \
    EMBEDDING_PROVIDER=openai_compatible \
    EMBEDDING_MODEL=nomic-embed-text \
    EMBEDDING_ENDPOINT=http://host.docker.internal:11434/v1 \
    EMBEDDING_API_KEY=ollama \
    EMBEDDING_DIMENSIONS=768
VOLUME ["/data"]
EXPOSE 8000
CMD ["python", "-m", "patchmind.server"]
