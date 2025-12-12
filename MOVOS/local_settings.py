# Local development overrides for MOVOS
# This file is not tracked in git (should be added to .gitignore).

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'movos',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        # Use explicit IPv4 to avoid resolution to IPv6 (::1) which can cause
        # connection refused when Docker maps host port to container.
        'HOST': '127.0.0.1',
        'PORT': '5433',
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
