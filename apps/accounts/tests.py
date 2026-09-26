from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import Hero, Profile, Role, SteamAccount
from .services import STEAM_ID64_OFFSET

User = get_user_model()


class RegistrationTests(TestCase):
    def test_registration_creates_an_empty_profile(self):
        response = self.client.post(
            reverse('accounts:register'),
            {
                'username': 'crystal_maiden',
                'email': 'cm@example.com',
                'password1': 'Safe-password-123',
                'password2': 'Safe-password-123',
            },
        )

        user = User.objects.get(username='crystal_maiden')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('profile_edit'))


class SteamConnectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='steam_user', password='Safe-password-123')
        self.client.force_login(self.user)

    def test_connect_starts_a_steam_openid_request(self):
        response = self.client.get(reverse('accounts:steam_connect'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('https://steamcommunity.com/openid/login?'))
        self.assertIn('steam_openid_state', self.client.session)

    @patch('apps.accounts.views.refresh_dota_statistics')
    @patch('apps.accounts.views.verify_steam_response')
    def test_verified_callback_links_the_steam_account(self, verify_response, refresh_statistics):
        steam_id = STEAM_ID64_OFFSET + 123456
        verify_response.return_value = steam_id
        session = self.client.session
        session['steam_openid_state'] = 'verified-state'
        session.save()

        response = self.client.get(
            f"{reverse('accounts:steam_callback')}?state=verified-state&openid.claimed_id=https%3A%2F%2Fsteamcommunity.com%2Fopenid%2Fid%2F{steam_id}"
        )

        account = SteamAccount.objects.get(user=self.user)
        self.assertEqual(account.steam_id, steam_id)
        self.assertEqual(account.account_id, 123456)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.steam_id, f'https://steamcommunity.com/profiles/{steam_id}/')
        refresh_statistics.assert_called_once_with(account)
        self.assertRedirects(response, reverse('accounts:steam_stats'))

    def test_callback_rejects_missing_state(self):
        response = self.client.get(reverse('accounts:steam_callback'))
        self.assertEqual(response.status_code, 400)

    def test_stats_page_requires_connected_account(self):
        response = self.client.get(reverse('accounts:steam_stats'))
        self.assertEqual(response.status_code, 404)

    def test_disconnect_removes_only_current_users_connection(self):
        SteamAccount.objects.create(user=self.user, steam_id=STEAM_ID64_OFFSET + 9, account_id=9)

        response = self.client.post(reverse('accounts:steam_disconnect'))

        self.assertRedirects(response, reverse('profile_edit'))
        self.assertFalse(SteamAccount.objects.filter(user=self.user).exists())

    def test_profile_edit_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('profile_edit'))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('profile_edit')}")

    def test_logged_in_user_is_redirected_away_from_login_page(self):
        user = User.objects.create_user(username='already_logged_in', password='Safe-password-123')
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:login'))

        self.assertRedirects(response, reverse('profile_edit'))

    def test_profile_edit_does_not_accept_a_manually_entered_mmr(self):
        user = User.objects.create_user(username='juggernaut', password='Safe-password-123')
        self.client.force_login(user)
        response = self.client.post(reverse('profile_edit'), {'dota_nickname': 'Yurnero', 'mmr': 5000})
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.dota_nickname, 'Yurnero')
        self.assertIsNone(user.profile.mmr)
        self.assertRedirects(response, reverse('profile_detail', kwargs={'username': user.username}))

    def test_public_profile_hides_empty_data(self):
        self.client.logout()
        user = User.objects.create_user(username='empty_profile', password='Safe-password-123')
        response = self.client.get(reverse('profile_detail', kwargs={'username': user.username}))
        self.assertContains(response, 'This profile is empty')
        self.assertNotContains(response, 'Game information')

    def test_profile_page_recovers_a_missing_profile(self):
        user = User.objects.create_user(username='legacy_account', password='Safe-password-123')
        user.profile.delete()

        response = self.client.get(reverse('profile_detail', kwargs={'username': user.username}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_profile_can_store_roles_and_favourite_heroes(self):
        user = User.objects.create_user(username='earthshaker', password='Safe-password-123')
        role = Role.objects.get(position=2)
        hero = Hero.objects.get(slug='earthshaker')
        self.client.force_login(user)

        response = self.client.post(reverse('profile_edit'), {
            'preferred_roles': [role.pk], 'favorite_heroes': [hero.pk],
        })

        self.assertRedirects(response, reverse('profile_detail', kwargs={'username': user.username}))
        self.assertContains(self.client.get(reverse('profile_detail', kwargs={'username': user.username})), 'Earthshaker')

    def test_profile_accepts_multiple_favourite_heroes_and_a_valid_timezone(self):
        user = User.objects.create_user(username='multi_pick', password='Safe-password-123')
        self.client.force_login(user)
        heroes = Hero.objects.filter(slug__in=('axe', 'pudge'))

        response = self.client.post(reverse('profile_edit'), {
            'favorite_heroes': list(heroes.values_list('pk', flat=True)),
            'timezone': 'GMT+2',
        })

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.favorite_heroes.count(), 2)
        self.assertEqual(user.profile.timezone, 'GMT+2')
        self.assertEqual(response.status_code, 302)
