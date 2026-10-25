FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app \
    FLASK_ENV=production \
    DATABASE_PATH=/app/instance/monitoring.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxcb1 \
        libglib2.0-0 \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/instance

EXPOSE 5000

CMD ["python", "-m", "flask", "--app", "app", "run", "--host", "0.0.0.0", "--port", "5000"]
