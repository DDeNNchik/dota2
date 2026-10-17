from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.http import QueryDict

from .models import SteamAccount
from .services import (
    STEAM_ID64_OFFSET,
    SteamServiceError,
    refresh_dota_statistics,
    steam_openid_url,
    verify_steam_response,
)


User = get_user_model()


class SteamOpenIDServiceTests(TestCase):
    def test_openid_url_contains_return_url_and_realm(self):
        url = steam_openid_url('https://site.test/callback?a=1', 'https://site.test/')

        self.assertIn('openid.mode=checkid_setup', url)
        self.assertIn('openid.return_to=https%3A%2F%2Fsite.test%2Fcallback%3Fa%3D1', url)
        self.assertIn('openid.realm=https%3A%2F%2Fsite.test%2F', url)

    def test_verification_rejects_invalid_or_non_account_identity(self):
        invalid_claims = (
            '',
            'https://example.test/id/123',
            f'https://steamcommunity.com/openid/id/not-a-number',
            f'https://steamcommunity.com/openid/id/{STEAM_ID64_OFFSET}',
        )
        for claimed_id in invalid_claims:
            with self.subTest(claimed_id=claimed_id), self.assertRaises(SteamServiceError):
                verify_steam_response({'openid.claimed_id': claimed_id})

    @patch('apps.accounts.services.urlopen')
    def test_verification_posts_assertion_and_returns_steam_id(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'is_valid:true\n'
        urlopen.return_value = response
        steam_id = STEAM_ID64_OFFSET + 77
        parameters = QueryDict('', mutable=True)
        parameters.appendlist('openid.claimed_id', f'https://steamcommunity.com/openid/id/{steam_id}')
        parameters.appendlist('openid.sig', 'signature')

        result = verify_steam_response(parameters)

        self.assertEqual(result, steam_id)
        request = urlopen.call_args.args[0]
        self.assertIn(b'openid.mode=check_authentication', request.data)
        self.assertIn(b'openid.sig=signature', request.data)

    @patch('apps.accounts.services.urlopen')
    def test_verification_rejects_unverified_or_unreachable_provider(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'is_valid:false\n'
        urlopen.return_value = response
        parameters = QueryDict('', mutable=True)
        parameters['openid.claimed_id'] = f'https://steamcommunity.com/openid/id/{STEAM_ID64_OFFSET + 1}'

        with self.assertRaisesRegex(SteamServiceError, 'did not verify'):
            verify_steam_response(parameters)

        urlopen.side_effect = TimeoutError
        with self.assertRaisesRegex(SteamServiceError, 'could not verify'):
            verify_steam_response(parameters)


class RefreshDotaStatisticsTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='steam_stats_user', password='testpass')
        self.account = SteamAccount.objects.create(
            user=user,
            steam_id=STEAM_ID64_OFFSET + 123,
            account_id=123,
            persona_name='Old name',
            avatar_url='https://example.test/old.jpg',
            profile_url='https://example.test/old-profile',
        )

    @patch('apps.esports.services.opendota.OpenDotaClient')
    def test_refresh_stores_profile_stats_and_only_ten_recent_matches(self, client_class):
        client = client_class.return_value
        client.player.return_value = {
            'profile': {
                'personaname': 'New name',
                'avatarfull': 'https://example.test/new.jpg',
                'profileurl': 'https://example.test/new-profile',
                'fh_unavailable': False,
            },
            'rank_tier': 80,
            'mmr_estimate': {'estimate': 6300},
            'computed_mmr': 5000,
        }
        client.win_loss.return_value = {'win': 30, 'lose': 20}
        client.get_json.return_value = [
            {'match_id': match_id, 'radiant_win': True, 'player_slot': 0}
            for match_id in range(12)
        ]

        result = refresh_dota_statistics(self.account)

        self.account.refresh_from_db()
        self.assertIs(result, self.account)
        self.assertEqual((self.account.persona_name, self.account.mmr_estimate), ('New name', 6300))
        self.assertEqual(self.account.avatar_url, 'https://example.test/new.jpg')
        self.assertEqual(self.account.profile_url, 'https://example.test/new-profile')
        self.assertEqual((self.account.wins, self.account.losses), (30, 20))
        self.assertEqual(len(self.account.recent_matches), 10)
        self.assertTrue(all(match['won'] for match in self.account.recent_matches))
        self.assertTrue(self.account.match_history_available)
        self.assertIsNotNone(self.account.stats_updated_at)
        client.player.assert_called_once_with(123)
        client.win_loss.assert_called_once_with(123)

    @patch('apps.esports.services.opendota.OpenDotaClient')
    def test_refresh_uses_computed_mmr_and_marks_unavailable_history(self, client_class):
        client = client_class.return_value
        client.player.return_value = {
            'profile': {'fh_unavailable': True},
            'computed_mmr': 5123.6,
        }
        client.win_loss.return_value = {}
        client.get_json.return_value = {'error': 'history unavailable'}

        refresh_dota_statistics(self.account)

        self.account.refresh_from_db()
        self.assertEqual(self.account.mmr_estimate, 5124)
        self.assertFalse(self.account.match_history_available)
        self.assertEqual(self.account.recent_matches, [])
        self.assertEqual((self.account.wins, self.account.losses), (0, 0))

    @patch('apps.esports.services.opendota.OpenDotaClient')
    def test_refresh_maps_provider_failure_to_steam_service_error(self, client_class):
        from apps.esports.services.opendota import ExternalDataError

        client_class.return_value.player.side_effect = ExternalDataError('offline')

        with self.assertRaises(SteamServiceError):
            refresh_dota_statistics(self.account)

        self.account.refresh_from_db()
        self.assertEqual(self.account.persona_name, 'Old name')
