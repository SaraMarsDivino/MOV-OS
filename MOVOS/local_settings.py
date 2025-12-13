
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

DEBUG = True

# Default: use SQLite for quick local development.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}

# Allow overriding to Postgres (docker-compose) using env vars.
# Set USE_COMPOSE_DB=1 or POSTGRES_HOST to enable.
USE_COMPOSE_DB = os.environ.get('USE_COMPOSE_DB', '') == '1'
POSTGRES_HOST = os.environ.get('POSTGRES_HOST')
if USE_COMPOSE_DB or POSTGRES_HOST:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB', 'movos'),
            'USER': os.environ.get('POSTGRES_USER', 'movos'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'movos'),
            'HOST': POSTGRES_HOST or os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        }
    }

try:
    ALLOWED_HOSTS
except NameError:
    ALLOWED_HOSTS = []
for h in ("localhost", "127.0.0.1", "0.0.0.0"):
    if h not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(h)

