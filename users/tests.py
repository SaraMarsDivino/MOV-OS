import time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


User = get_user_model()


class SessionMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tester_session',
            password='StrongPass123!',
        )

    @override_settings(AUTO_LOGOUT_DELAY=1)
    def test_auto_logout_logs_out_inactive_user(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['last_activity'] = time.time() - 30
        session.save()

        response = self.client.get('/cashier/api/bootstrap/', HTTP_ACCEPT='text/html')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(AUTO_LOGOUT_DELAY=None)
    def test_auto_logout_disabled_keeps_user_logged_in(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['last_activity'] = time.time() - 60 * 60 * 24
        session.save()

        response = self.client.get('/cashier/api/bootstrap/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('_auth_user_id', self.client.session)


class RedirectOn404MiddlewareTests(TestCase):
    def test_anonymous_html_404_redirects_to_login(self):
        response = self.client.get('/ruta/que/no/existe/', HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        self.assertIn('next=', response.url)
