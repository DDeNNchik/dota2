from django.test import TestCase
from django.urls import reverse


class SetLanguageViewTests(TestCase):
    def test_rejects_non_post_requests(self):
        response = self.client.get(reverse('set_language'))

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.headers['Allow'], 'POST')

    def test_sets_supported_language_and_redirects_to_local_next_url(self):
        response = self.client.post(reverse('set_language'), {
            'language': 'uk',
            'next': '/players/',
        })

        self.assertRedirects(response, '/players/', fetch_redirect_response=False)
        self.assertEqual(response.cookies['django_language'].value, 'uk')
        self.assertEqual(response.cookies['django_language']['samesite'], 'Lax')

    def test_unsafe_redirect_falls_back_to_home(self):
        response = self.client.post(reverse('set_language'), {
            'language': 'en',
            'next': 'https://evil.example/steal-session',
        })

        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_unsupported_language_does_not_set_language_cookie(self):
        response = self.client.post(reverse('set_language'), {
            'language': 'xx',
            'next': '/players/',
        })

        self.assertRedirects(response, '/players/', fetch_redirect_response=False)
        self.assertNotIn('django_language', response.cookies)

    def test_referer_is_used_when_next_is_missing(self):
        response = self.client.post(
            reverse('set_language'),
            {'language': 'en'},
            HTTP_REFERER='/news/',
        )

        self.assertRedirects(response, '/news/', fetch_redirect_response=False)
