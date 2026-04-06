FROM python:latest

WORKDIR /api

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install docker CLI for backup script and cron
RUN apt-get update && apt-get install -y \
    docker.io \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY ./api ./api

# Copy Alembic configuration and migrations
COPY alembic ./alembic

# Copy backup scripts and make them executable
COPY ./api/backup.sh /api/backup.sh
COPY ./api/restore.sh /api/restore.sh
RUN chmod +x /api/backup.sh /api/restore.sh

# Copy cron file with proper format
COPY ./api/backup.cron /etc/cron.d/ym-backup
RUN chmod 0644 /etc/cron.d/ym-backup

EXPOSE 8000

# Start cron in background and then run FastAPI
CMD cron && fastapi run main.py --host 0.0.0.0 --port 8000
