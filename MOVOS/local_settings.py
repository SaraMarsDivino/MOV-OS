# Local development overrides for MOVOS
# This file is not tracked in git (should be added to .gitignore).

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'movos',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        # In Docker the DB runs in a separate container. Use the compose service
        # name and the internal Postgres port so the web container can reach it.
        'HOST': 'db',
        'PORT': '5432',
    }
}

# Allow local hosts during development
try:
    ALLOWED_HOSTS
except NameError:
    ALLOWED_HOSTS = []

for h in ('localhost', '127.0.0.1'):
    if h not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(h)

# Disable auto-logout during local development so sessions do not expire.
AUTO_LOGOUT_DELAY = None
