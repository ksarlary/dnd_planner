FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build args allow matching host UID/GID (defaults are set in compose)
ARG APP_UID=1000
ARG APP_GID=1000

# Create user/group
RUN groupadd -g ${APP_GID} appgroup \
    && useradd -m -u ${APP_UID} -g ${APP_GID} appuser

# Install deps first (better Docker layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application files
COPY bot.py /app/bot.py
COPY config.json /app/config.json

# Ensure data directory exists and is writable
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

USER appuser

CMD ["python", "bot.py"]
