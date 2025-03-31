FROM python:3.11-slim

WORKDIR /app

# Install cron + curl + other system deps
RUN apt-get update && \
    apt-get install -y cron curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your app files and crontab file
COPY fdp_backup.py .
COPY crontab /etc/cron.d/fdp-cron
COPY config /app/config

# Give execution rights and install crontab
RUN chmod 0644 /etc/cron.d/fdp-cron && \
    crontab /etc/cron.d/fdp-cron

# Create the log directory if it doesn't exist
RUN mkdir -p /app/backup

# Start cron in foreground
CMD ["cron", "-f"]
