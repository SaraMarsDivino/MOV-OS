#!/usr/bin/env sh
set -e

if [ "$DB_ENGINE" = "postgres" ]; then
  echo "Waiting for Postgres..."
  until python -c "import sys,psycopg2; import os; psycopg2.connect(dbname=os.getenv('POSTGRES_DB','movos'), user=os.getenv('POSTGRES_USER','movos'), password=os.getenv('POSTGRES_PASSWORD','movos'), host=os.getenv('POSTGRES_HOST','db'), port=int(os.getenv('POSTGRES_PORT','5432')))"; do
    echo "Postgres is unavailable - sleeping"
    sleep 2
  done
fi

echo "Running migrations"
python manage.py migrate --noinput

echo "Collecting static files"
python manage.py collectstatic --noinput || true

# Optionally create a superuser on first run if env vars are provided
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "Ensuring superuser $DJANGO_SUPERUSER_USERNAME exists"
  python - <<'PY'
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MOVOS.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', f"{username}@example.com")
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if not username or not password:
  raise SystemExit(0)
u, created = User.objects.get_or_create(username=username, defaults={"email": email, "is_staff": True, "is_superuser": True})
if not created:
  # Ensure flags in case user existed without superuser perms
  changed = False
  if not u.is_staff:
    u.is_staff = True; changed = True
  if not u.is_superuser:
    u.is_superuser = True; changed = True
  if changed:
    u.save()
u.set_password(password)
u.save()
print(f"Superuser '{username}' ready (created={created})")
PY
fi

# Optional: import products on boot if a path/url is provided (streaming, low memory)
if [ -n "$IMPORT_PRODUCTS_PATH" ]; then
  echo "Importing products from $IMPORT_PRODUCTS_PATH (dry-run=${IMPORT_PRODUCTS_DRY_RUN:-false})"
  if [ "${IMPORT_PRODUCTS_DRY_RUN:-false}" = "true" ]; then
    python manage.py import_products "$IMPORT_PRODUCTS_PATH" --dry-run --batch "${IMPORT_PRODUCTS_BATCH:-500}" || true
  else
    python manage.py import_products "$IMPORT_PRODUCTS_PATH" --batch "${IMPORT_PRODUCTS_BATCH:-500}" || true
  fi
fi

exec "$@"
