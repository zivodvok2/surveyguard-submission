FROM node:20-slim AS frontend

WORKDIR /ui
COPY datasense-ui/package.json datasense-ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY datasense-ui/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY requirements-api.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements-api.txt

COPY . .
COPY --from=frontend /ui/dist ./datasense-ui/dist

RUN useradd --create-home --uid 10001 servallab \
    && chown -R servallab:servallab /app
USER servallab

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
