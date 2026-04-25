FROM python:3.13-slim

# Avoid creating .pyc files + ensure stdout/stderr unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (optional; uncomment if you need build tools)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY bot/ ./bot/

# Expect DISCORD_TOKEN via env or secrets
CMD ["python", "main.py"]
