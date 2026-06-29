FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/app/.data/uv-cache \
    HOME=/app

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

RUN addgroup --system foundry && adduser --system --ingroup foundry foundry \
    && mkdir -p /app/.data && chown -R foundry:foundry /app

USER foundry
EXPOSE 8000

CMD [".venv/bin/uvicorn", "foundry.main:app", "--host", "0.0.0.0", "--port", "8000"]
