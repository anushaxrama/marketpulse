FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy TZ=UTC SPARK_LOCAL_IP=127.0.0.1
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.13.6
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --extra spark --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH" PYSPARK_PYTHON=/app/.venv/bin/python PYSPARK_DRIVER_PYTHON=/app/.venv/bin/python
COPY infra/resolve_jars.py /tmp/resolve_jars.py
RUN python /tmp/resolve_jars.py
COPY marketpulse ./marketpulse
COPY services ./services
COPY warehouse ./warehouse
RUN uv sync --frozen --extra spark --no-dev && useradd -u 1851 -m marketpulse && mkdir -p /data && chown marketpulse:marketpulse /app /data
USER marketpulse
CMD ["marketpulse","worker"]
