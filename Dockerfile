FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# git is needed by the git_status / git_commit / git_log tools.
# safe.directory '*' stops git refusing the bind-mounted workspace as "dubious ownership".
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server ./server
COPY templates ./templates
COPY docker/healthcheck.py ./healthcheck.py

# Run as a normal user, not root.
RUN useradd --create-home appuser \
    && mkdir -p /app/workspace /app/logs \
    && chown -R appuser /app
USER appuser

ENV MCP_HOST=0.0.0.0 MCP_PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "/app/healthcheck.py"]

CMD ["python", "-m", "server.main"]
