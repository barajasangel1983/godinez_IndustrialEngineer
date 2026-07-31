# ── Stage 1: Build dependencies ───────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

# gcc + libpq-dev needed to compile psycopg2 from source
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install into /install so we can copy cleanly into the runtime image.
# psycopg2-binary added here (not in requirements.txt) — only needed at runtime.
RUN pip install --no-cache-dir --prefix=/install \
        -r requirements.txt \
        "psycopg2-binary>=2.9"


# ── Stage 2: Production image ─────────────────────────────────────
FROM python:3.13-slim AS production

LABEL org.opencontainers.image.title="Godínez IndustrialEngineer" \
      org.opencontainers.image.description="AI-powered manufacturing analysis agent" \
      org.opencontainers.image.version="0.6.0"

# libpq5 = PostgreSQL client runtime library (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd -r godinez && useradd -r -g godinez -d /app -s /sbin/nologin godinez

WORKDIR /app

# Installed packages from builder stage
COPY --from=builder /install /usr/local

# Application source
COPY src/       ./src/
COPY alembic/   ./alembic/
COPY alembic.ini ./alembic.ini
COPY main.py    ./main.py
COPY scripts/   ./scripts/

# Writable data directory (mounted as a volume in production)
RUN mkdir -p data && \
    chmod +x scripts/start.sh && \
    chown -R godinez:godinez /app

USER godinez

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# start.sh: wait for DB → run migrations → exec uvicorn
CMD ["./scripts/start.sh"]
