FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ── Dependencies ───────────────────────────────────────────────────────────────
FROM base AS deps
RUN pip install --no-cache-dir pip --upgrade
COPY backend/packages/py-logger /app/packages/py-logger
RUN pip install --no-cache-dir /app/packages/py-logger
COPY backend/services/mail-sync/pyproject.toml /app/
RUN pip install --no-cache-dir .

# ── Production ─────────────────────────────────────────────────────────────────
FROM base AS runner
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY backend/services/mail-sync/src /app/src
USER appuser
EXPOSE 4003
CMD ["uvicorn", "src.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "4003"]
