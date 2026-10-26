# The platform in one image: the pmd CLI (sources, dbt build, gates, publish), the API and the console it serves.
# It needs PostgreSQL (PMD_DATABASE_URL); compose.yaml starts one, with Redpanda for the payment topic.
FROM node:22-slim AS console
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PMD_ROOT=/app PMD_DATA=/app/data PMD_WEB=/app/web/dist
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[kafka]"
COPY config ./config
COPY warehouse ./warehouse
COPY dags ./dags
COPY heldout ./heldout
COPY reports ./reports
COPY --from=console /web/dist ./web/dist
RUN useradd --uid 10001 --no-create-home pmd \
    && mkdir -p /app/data /app/warehouse/target /app/warehouse/logs \
    && chown -R pmd /app/data /app/warehouse /app/reports
USER pmd
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["pmd", "serve", "--host", "0.0.0.0", "--port", "8000"]
