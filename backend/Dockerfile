FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# lightgbm và xgboost cần libgomp; ảnh slim không có sẵn.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY backend ./backend
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "fastapi", "run", "backend/app/main.py", "--host", "0.0.0.0", "--port", "8000"]
