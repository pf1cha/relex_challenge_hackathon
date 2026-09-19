FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RELEX_FRONTEND_DIST=/app/frontend/dist
WORKDIR /app
RUN addgroup --system relex && adduser --system --ingroup relex --home /nonexistent relex
COPY backend/ ./backend/
RUN pip install --no-cache-dir './backend[evidence,intelligence,product]'
COPY --from=frontend /build/frontend/dist ./frontend/dist
USER relex
EXPOSE 18080
CMD ["uvicorn", "app.main:production_app", "--factory", "--host", "0.0.0.0", "--port", "18080", "--no-access-log"]
