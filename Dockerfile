FROM python:3.11-slim

WORKDIR /app

# Install cron and dependencies
RUN apt-get update && \
    apt-get install -y cron && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY fdp_backup.py .
COPY serve_logs.py .
COPY dashboard.html .

# Copy default crontab (will be mounted in prod)
RUN touch /etc/cron.d/fdp-cron && chmod 0644 /etc/cron.d/fdp-cron

# Start cron + log dashboard
CMD sh -c "crontab /etc/cron.d/fdp-cron && cron && python /app/serve_logs.py"
