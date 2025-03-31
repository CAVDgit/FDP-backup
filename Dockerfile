FROM python:3.11-slim

WORKDIR /app

# Install supercronic and dependencies
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL -o /usr/local/bin/supercronic https://github.com/aptible/supercronic/releases/download/v0.2.4/supercronic-linux-amd64 && \
    chmod +x /usr/local/bin/supercronic && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fdp_backup.py .

# Entry script creates cron file and starts supercronic
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
