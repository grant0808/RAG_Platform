FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY src ./src

RUN addgroup --system foundry && adduser --system --ingroup foundry foundry \
    && mkdir -p /app/.data && chown -R foundry:foundry /app

USER foundry
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "foundry.main:app", "--host", "0.0.0.0", "--port", "8000"]

