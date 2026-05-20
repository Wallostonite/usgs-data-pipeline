FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Ensure the pipeline package is importable from /app/src
ENV PYTHONPATH=/app/src

WORKDIR /app

# gcc is only needed for the pip build step; remove it afterwards to reduce image size.
# psycopg2-binary bundles its own libpq, so only cron is needed at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    cron \
    && pip install --upgrade pip \
    && apt-get purge -y --auto-remove gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Register the cron schedule
COPY docker/crontab /etc/cron.d/pipeline-cron
RUN chmod 0644 /etc/cron.d/pipeline-cron && crontab /etc/cron.d/pipeline-cron

RUN touch /var/log/cron.log

# Run as non-root user
RUN useradd --no-create-home --shell /bin/false appuser
RUN chown appuser /var/log/cron.log

# Export only the specific vars cron needs — never dump the full environment
CMD ["sh", "-c", \
  "printf 'DATABASE_URL=%s\\nMIN_MAGNITUDE=%s\\nLOOKBACK_DAYS=%s\\nSLACK_WEBHOOK_URL=%s\\nPYTHONPATH=/app/src\\n' \
   \"$DATABASE_URL\" \"$MIN_MAGNITUDE\" \"$LOOKBACK_DAYS\" \"$SLACK_WEBHOOK_URL\" \
   > /etc/environment && cron && tail -f /var/log/cron.log"]
