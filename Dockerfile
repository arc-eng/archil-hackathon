# The golden-sandbox connector on Cloud Run (arc-eng/hq#781). Secrets come in as env, never baked in.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY *.py ./
CMD ["uv", "run", "--frozen", "--no-dev", "connector.py"]
