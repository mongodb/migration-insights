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
    MI_LOG_JSON=true \
    MI_KANOPY_IDENTITY=true \
    PYTHONUNBUFFERED=1

EXPOSE 3030

CMD ["gunicorn", "--workers=1", "--threads=4", "--worker-class=gthread", "--bind=0.0.0.0:3030", "--timeout=3600", "--graceful-timeout=30", "--access-logfile=-", "--error-logfile=-", "migration_insights:app"]
