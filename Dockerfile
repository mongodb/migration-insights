FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY migration_insights.py ./
COPY blueprints ./blueprints
COPY lib ./lib
COPY templates ./templates
COPY static ./static
COPY images ./images

ENV MI_HOST=0.0.0.0 \
    MI_PORT=3030 \
    MI_SSL_ENABLED=false \
    MI_LOG_FILE=/tmp/insights.log \
    PYTHONUNBUFFERED=1

EXPOSE 3030

CMD ["python3", "migration_insights.py"]
