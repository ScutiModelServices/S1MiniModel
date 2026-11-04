# syntax=docker/dockerfile:1
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV S1MINI_WEB_DIR=/app/web S1MINI_TOKENS_FILE=/data/tokens.json PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH" HF_HOME=/models S1MINI_HOST=0.0.0.0
WORKDIR /app

# uv.lock pins torch to the CPU-only index (see pyproject.toml), so no CUDA/Triton wheels are pulled.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
RUN python -c "import torch; assert torch.version.cuda is None and torch.version.hip is None, 'CPU-only torch required'"
COPY src ./src
COPY web ./web

EXPOSE 9220
CMD ["python", "src/app.py"]
