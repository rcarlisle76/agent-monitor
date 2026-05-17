# Stage 1 — build React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2 — combined runtime
FROM python:3.12-slim

# Install Nginx and Supervisord
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor \
    && rm -rf /var/lib/apt/lists/*

# Python backend
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .

# React build output
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# Config files
COPY deploy/nginx.conf /etc/nginx/sites-available/default
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Remove default nginx site and enable ours
RUN rm -f /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

VOLUME ["/app/data"]
EXPOSE 3000

ENV DB_PATH=/app/data/agent_monitor.db
ENV ACCURACY_FLAG_THRESHOLD=70.0

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
