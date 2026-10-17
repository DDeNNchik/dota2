from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Hero, Profile, Role, SteamAccount
from .services import STEAM_ID64_OFFSET, SteamServiceError


User = get_user_model()


class ProfileModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        # The post_save signal creates each user's profile automatically.
        self.profile = self.user.profile
        self.profile.description = 'Test bio'
        self.profile.save(update_fields=('description',))

    def test_user_creation_creates_an_empty_profile(self):
        user = User.objects.create_user(username='another_user', password='testpass')

        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.description, '')

    def test_profile_creation(self):
        self.assertEqual(self.profile.user.username, 'testuser')
        self.assertEqual(self.profile.description, 'Test bio')

    def test_profile_str_method(self):
        self.assertEqual(str(self.profile), 'Профиль testuser')


class RegistrationTests(TestCase):
    def test_registration_creates_user_and_empty_profile(self):
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
        self.assertRedirects(response, reverse('profile_edit'))
        self.assertTrue(user.profile)
        self.assertEqual(user.profile.description, '')


class PlayerSearchTests(TestCase):
    def test_search_matches_registered_dota_nickname_and_returns_site_profile(self):
        user = User.objects.create_user(username='registered_user', password='testpass')
        user.profile.dota_nickname = 'Pupsik'
        user.profile.save(update_fields=('dota_nickname',))
        User.objects.create_user(username='other_player', password='testpass')

        response = self.client.get(reverse('player_search'), {'q': 'pupsik'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [{
            'nickname': 'Pupsik',
            'username': 'registered_user',
            'avatar_url': '',
            'url': reverse('profile_detail', kwargs={'username': 'registered_user'}),
        }])

    def test_search_matches_username_and_steam_persona_name(self):
        username_match = User.objects.create_user(username='PupsikFan', password='testpass')
        persona_match = User.objects.create_user(username='steam_user', password='testpass')
        SteamAccount.objects.create(
            user=persona_match,
            steam_id=STEAM_ID64_OFFSET + 100,
            account_id=100,
            persona_name='Pupsik Pro',
        )

        response = self.client.get(reverse('player_search'), {'q': 'pupsik'})

        results = response.json()['results']
        self.assertEqual([item['username'] for item in results], ['PupsikFan', 'steam_user'])
        self.assertEqual(results[0]['url'], reverse('profile_detail', kwargs={'username': username_match.username}))
        self.assertEqual(results[1]['nickname'], 'Pupsik Pro')

    def test_search_returns_no_results_for_short_query(self):
        User.objects.create_user(username='pupsik', password='testpass')

        response = self.client.get(reverse('player_search'), {'q': 'p'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'results': []})


class SteamConnectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='steam_user', password='Safe-password-123')
        self.client.force_login(self.user)

    def test_connect_starts_a_steam_openid_request_and_stores_state(self):
        response = self.client.get(reverse('accounts:steam_connect'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('https://steamcommunity.com/openid/login?'))
        state = self.client.session['steam_openid_state']
        self.assertTrue(state)
        self.assertIn(state, response['Location'])

    @patch('apps.accounts.views.refresh_dota_statistics')
    @patch('apps.accounts.views.verify_steam_response')
    def test_verified_callback_links_steam_and_refreshes_statistics(self, verify_response, refresh_statistics):
        steam_id = STEAM_ID64_OFFSET + 123456
        verify_response.return_value = steam_id
        session = self.client.session
        session['steam_openid_state'] = 'verified-state'
        session.save()

        response = self.client.get(reverse('accounts:steam_callback'), {
            'state': 'verified-state',
            'openid.claimed_id': f'https://steamcommunity.com/openid/id/{steam_id}',
        })

        account = SteamAccount.objects.get(user=self.user)
        self.assertEqual(account.steam_id, steam_id)
        self.assertEqual(account.account_id, 123456)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.steam_id, f'https://steamcommunity.com/profiles/{steam_id}/')
        verify_response.assert_called_once()
        refresh_statistics.assert_called_once_with(account)
        self.assertRedirects(response, reverse('accounts:steam_stats'))

    def test_callback_rejects_missing_state(self):
        response = self.client.get(reverse('accounts:steam_callback'))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(SteamAccount.objects.filter(user=self.user).exists())

    def test_callback_rejects_mismatched_state_without_verifying_steam(self):
        session = self.client.session
        session['steam_openid_state'] = 'expected-state'
        session.save()

        with patch('apps.accounts.views.verify_steam_response') as verify_response:
            response = self.client.get(reverse('accounts:steam_callback'), {'state': 'wrong-state'})

        self.assertEqual(response.status_code, 400)
        verify_response.assert_not_called()

    @patch('apps.accounts.views.refresh_dota_statistics', side_effect=SteamServiceError('OpenDota unavailable'))
    @patch('apps.accounts.views.verify_steam_response')
    def test_verified_connection_is_kept_if_initial_stats_refresh_fails(self, verify_response, refresh_statistics):
        steam_id = STEAM_ID64_OFFSET + 123456
        verify_response.return_value = steam_id
        session = self.client.session
        session['steam_openid_state'] = 'verified-state'
        session.save()

        response = self.client.get(reverse('accounts:steam_callback'), {
            'state': 'verified-state',
            'openid.claimed_id': f'https://steamcommunity.com/openid/id/{steam_id}',
        })

        self.assertTrue(SteamAccount.objects.filter(user=self.user, steam_id=steam_id).exists())
        self.assertRedirects(response, reverse('accounts:steam_stats'))
        self.assertContains(self.client.get(response['Location']), 'Connected Steam account')
        refresh_statistics.assert_called_once()

    def test_stats_page_requires_connected_account(self):
        response = self.client.get(reverse('accounts:steam_stats'))

        self.assertEqual(response.status_code, 404)

    def test_disconnect_removes_only_current_users_connection(self):
        other_user = User.objects.create_user(username='another_steam_user', password='testpass')
        account = SteamAccount.objects.create(
            user=self.user,
            steam_id=STEAM_ID64_OFFSET + 9,
            account_id=9,
        )
        other_account = SteamAccount.objects.create(
            user=other_user,
            steam_id=STEAM_ID64_OFFSET + 10,
            account_id=10,
        )

        response = self.client.post(reverse('accounts:steam_disconnect'))

        self.assertRedirects(response, reverse('profile_edit'))
        self.assertFalse(SteamAccount.objects.filter(pk=account.pk).exists())
        self.assertTrue(SteamAccount.objects.filter(pk=other_account.pk).exists())

    def test_profile_edit_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse('profile_edit'))

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('profile_edit')}")

    def test_logged_in_user_is_redirected_away_from_login_page(self):
        response = self.client.get(reverse('accounts:login'))

        self.assertRedirects(response, reverse('profile_edit'))

    def test_profile_edit_does_not_accept_a_manually_entered_mmr(self):
        response = self.client.post(reverse('profile_edit'), {'dota_nickname': 'Yurnero', 'mmr': 5000})

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.dota_nickname, 'Yurnero')
        self.assertIsNone(self.user.profile.mmr)
        self.assertRedirects(response, reverse('profile_detail', kwargs={'username': self.user.username}))

    def test_public_profile_hides_empty_data(self):
        self.client.logout()
        user = User.objects.create_user(username='empty_profile', password='testpass')

        response = self.client.get(reverse('profile_detail', kwargs={'username': user.username}))

        self.assertContains(response, 'This profile is empty')
        self.assertNotContains(response, 'Game information')

    def test_profile_page_recovers_a_missing_profile(self):
        user = User.objects.create_user(username='legacy_account', password='testpass')
        user.profile.delete()

        response = self.client.get(reverse('profile_detail', kwargs={'username': user.username}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_profile_can_store_roles_and_favourite_heroes(self):
        role = Role.objects.get(position=2)
        hero = Hero.objects.get(slug='earthshaker')

        response = self.client.post(reverse('profile_edit'), {
            'preferred_roles': [role.pk],
            'favorite_heroes': [hero.pk],
        })

        self.assertRedirects(response, reverse('profile_detail', kwargs={'username': self.user.username}))
        self.assertContains(self.client.get(reverse('profile_detail', kwargs={'username': self.user.username})), 'Earthshaker')
        self.assertQuerySetEqual(self.user.profile.preferred_roles.all(), [role], transform=lambda item: item)

    def test_profile_accepts_multiple_favourite_heroes_and_a_valid_timezone(self):
        heroes = Hero.objects.filter(slug__in=('axe', 'pudge'))

        response = self.client.post(reverse('profile_edit'), {
            'favorite_heroes': list(heroes.values_list('pk', flat=True)),
            'timezone': 'GMT+2',
        })

        self.user.profile.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertQuerySetEqual(
            self.user.profile.favorite_heroes.order_by('slug'),
            list(heroes.order_by('slug')),
            transform=lambda item: item,
        )
        self.assertEqual(self.user.profile.timezone, 'GMT+2')
