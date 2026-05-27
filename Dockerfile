FROM node:20-bookworm-slim AS frontend-build

WORKDIR /build/frontend/pos-cashier

COPY frontend/pos-cashier/package*.json ./
RUN npm ci

COPY frontend/pos-cashier/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies (curated list compatible con ARM). Evitamos requirements.txt por encoding/paquetes pesados.
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir \
        Django==5.0.7 \
        gunicorn==23.0.0 \
        whitenoise==6.8.2 \
        psycopg2-binary==2.9.9 \
        djangorestframework==3.15.2 \
        djangorestframework-simplejwt==5.3.1 \
        openpyxl==3.1.5 \
        python-docx==1.1.2 \
        pillow==11.3.0 \
        pytz==2024.1 \
        tzdata==2024.1 \
        requests==2.32.3 \
        ujson==5.10.0 \
        simplejson==3.19.2

# Project files
COPY . .

# Bring in the built React assets so production images do not depend on host-side npm.
COPY --from=frontend-build /build/static/pos-cashier ./static/pos-cashier

# Collect static at build (optional)
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Entrypoint sets up DB and runs server
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
# Use $PORT if provided by the platform, else 8000. Tune workers/timeout for low-RAM free plans.
ENV WORKERS=2
ENV TIMEOUT=60
CMD ["sh", "-c", "gunicorn MOVOS.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WORKERS:-2} --timeout ${TIMEOUT:-60}"]
