FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.13.6
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY marketpulse ./marketpulse
COPY services ./services
COPY warehouse ./warehouse
RUN uv sync --frozen --no-dev && useradd -u 1851 -m marketpulse
ENV PATH="/app/.venv/bin:$PATH"
USER marketpulse
CMD ["marketpulse","serve"]
