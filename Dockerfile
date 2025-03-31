FROM python:3.11-slim

WORKDIR /app

# Install cron and dependencies
RUN apt-get update && \
    apt-get install -y cron && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fdp_backup.py .
COPY serve_logs.py .

# Run both: cron for backup + HTTP server for logs
CMD sh -c "crontab /etc/cron.d/fdp-cron && cron && python /app/serve_logs.py"
