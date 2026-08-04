FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1

WORKDIR /opt/evalforge

RUN pip install --no-cache-dir uv==0.8.2
COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv pip install --system .

RUN addgroup --system evalforge && adduser --system --ingroup evalforge evalforge \
    && chown -R evalforge:evalforge /opt/evalforge
USER evalforge

EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080"]

