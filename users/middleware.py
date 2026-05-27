import datetime
from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponsePermanentRedirect

class AutoLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Invalidate stale sessions when SESSION_VERSION is bumped in settings.
        # This lets the server force re-login across all browsers on deploy
        # without asking clients to clear cookies.
        expected_version = getattr(settings, 'SESSION_VERSION', None)
        if expected_version is not None and request.session.get('_sv') != expected_version:
            request.session.flush()
            login_url = getattr(settings, 'LOGIN_URL', '/login/')
            path = request.path
            static_url = getattr(settings, 'STATIC_URL', '/static/')
            if (not path.startswith(static_url)
                    and not path.startswith('/media/')
                    and not path.startswith(login_url)):
                return HttpResponseRedirect(f"{login_url}?next={path}")
            return HttpResponseRedirect(login_url)

        now = datetime.datetime.now().timestamp()
        max_idle = getattr(settings, 'AUTO_LOGOUT_DELAY', None)
        # If AUTO_LOGOUT_DELAY is None or non-positive, disable auto-logout
        if max_idle is None or (isinstance(max_idle, (int, float)) and max_idle <= 0):
            return self.get_response(request)
        last_activity = request.session.get('last_activity')
        if last_activity and now - last_activity > max_idle:
            logout(request)
        else:
            request.session['last_activity'] = now
        return self.get_response(request)


class CanonicalHostMiddleware:
    """Optionally redirect all requests to a canonical host.

    This helps avoid split sessions/cookies when the site is accessed via both
    www and non-www (or multiple hostnames).

    Configure with:
      - CANONICAL_HOST (e.g., "www.example.com" or "example.com")
      - CANONICAL_HOST_PERMANENT=1 to use 301 instead of 302
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        canonical_host = getattr(settings, 'CANONICAL_HOST', None)
        if not canonical_host:
            return self.get_response(request)

        try:
            request_host = request.get_host()
        except Exception:
            request_host = ''

        request_hostname = (request_host.split(':', 1)[0] or '').lower()
        canonical_hostname = (str(canonical_host).split(':', 1)[0] or '').lower()

        if request_hostname and canonical_hostname and request_hostname != canonical_hostname:
            path = request.get_full_path()
            scheme = 'https' if request.is_secure() else 'http'
            url = f"{scheme}://{canonical_host}{path}"
            permanent = str(getattr(settings, 'CANONICAL_HOST_PERMANENT', False)).lower() in (
                '1', 'true', 'yes', 'on'
            )
            return HttpResponsePermanentRedirect(url) if permanent else HttpResponseRedirect(url)

        return self.get_response(request)


class RedirectOn404Middleware:
    """If a view returns 404 and the user is not authenticated, redirect to login.

    This helps when sessions expire and the user lands on pages that would
    otherwise show a generic Not Found; instead we send them to the login
    page with `next` preserving the requested path.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            status = getattr(response, 'status_code', None)
        except Exception:
            status = None
        # Only redirect HTML requests (not API/json) and only when anonymous
        accept = request.META.get('HTTP_ACCEPT', '')
        if status == 404 and (not request.user.is_authenticated) and 'text/html' in accept:
            from django.conf import settings
            from django.shortcuts import redirect
            login_url = getattr(settings, 'LOGIN_URL', '/accounts/login/')
            # avoid redirect loops for the login page itself or static/media assets
            p = request.path
            if p.startswith(getattr(settings, 'STATIC_URL', '/static/')) or p.startswith('/media/'):
                return response
            if p == login_url or p.startswith(login_url):
                return response
            # safe redirect with next param
            return redirect(f"{login_url}?next={p}")
        return response