# -------------------------------
# Stage 1: Builder
# -------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --prefix=/install -r requirements.txt

# Copy application code
COPY . .

# -------------------------------
# Stage 2: Runtime
# -------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Set timezone
ENV TZ=UTC

# Install cron and timezone tools
RUN apt-get update && \
    apt-get install -y cron tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /install /usr/local
COPY --from=builder /app /app

# -------------------------------
# Setup Cron
# -------------------------------
# Copy cron file
COPY cron/2fa-cron /etc/cron.d/2fa-cron

# Give execution rights
RUN chmod 0644 /etc/cron.d/2fa-cron

# Apply cron job
RUN crontab /etc/cron.d/2fa-cron

# Create volume folders
RUN mkdir -p /data /cron
RUN chmod 755 /data /cron

# Expose port for FastAPI
EXPOSE 8080

# Start cron and API server together
CMD cron && uvicorn app:app --host 0.0.0.0 --port 8080
