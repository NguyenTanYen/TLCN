# ---- build giao diện React
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- API FastAPI + Pandas, phục vụ luôn giao diện đã build
FROM python:3.12-slim
WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-semantic.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# cổng ngữ nghĩa của gợi ý học liệu (torch CPU + MiniLM, ~1 GB); --build-arg SEMANTIC=0 để bỏ – gợi ý chỉ dùng BM25
ARG SEMANTIC=1
RUN if [ "$SEMANTIC" = "1" ]; then pip install --no-cache-dir -r requirements-semantic.txt \
      --extra-index-url https://download.pytorch.org/whl/cpu; fi
COPY database /app/database
COPY backend /app/backend
COPY --from=web /web/dist /app/frontend/dist
EXPOSE 8000
CMD ["sh", "-c", "python -m app.cli bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
