FROM python:latest

WORKDIR /api

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy application code
COPY ./api ./api

# Copy Alembic configuration and migrations
#COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

CMD ["fastapi", "run", "main.py", "--reload", "--host", "0.0.0.0", "--port", "8000"]

