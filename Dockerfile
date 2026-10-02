# One image that serves both halves: the frontend is built with Node, then handed to the
# Python backend, which serves it alongside the API. Two stages, so Node and the npm tree
# never ship to production.

# ---- build the frontend ------------------------------------------------------
FROM node:24-slim AS web
WORKDIR /src

# Dependencies first: this layer is cached until package-lock.json changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Type-checks and bundles; fails the build if the two sides of the API have drifted.
RUN npm run build

# ---- runtime -----------------------------------------------------------------
FROM python:3.14-slim AS runtime

# Unbuffered output so logs reach the platform immediately rather than sitting in a buffer.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UBF_ENV=production

WORKDIR /app

# The Postgres driver ships too, so UBF_DATABASE_URL can point at either SQLite or Postgres
# without rebuilding. It is a few megabytes and saves a surprise at deploy time.
COPY backend/requirements.txt backend/requirements-postgres.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -r backend/requirements-postgres.txt

COPY backend/ backend/
# app/main.py resolves the frontend as ../../frontend/dist, so keep that shape.
COPY --from=web /src/dist/ frontend/dist/

# The SQLite file and anything else written at runtime live here.
RUN useradd --create-home --uid 10001 ubf \
    && mkdir -p /data \
    && chown -R ubf:ubf /data /app
USER ubf

ENV UBF_DATABASE_URL=sqlite+aiosqlite:////data/ubf.db
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

WORKDIR /app/backend
# Honour the platform's $PORT when there is one (Render, Railway and friends set it).
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
