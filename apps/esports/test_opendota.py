from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

from django.test import TestCase

from .models import ProPlayer
from .services.opendota import (
    ExternalDataError,
    OpenDotaClient,
    normalise_name,
    refresh_player_stats,
    resolve_account_id,
)


class OpenDotaClientTests(TestCase):
    @patch('apps.esports.services.opendota.urlopen')
    def test_get_json_decodes_response_and_sends_user_agent(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"ok": true}'
        urlopen.return_value = response

        result = OpenDotaClient().get_json('/players/123')

        self.assertEqual(result, {'ok': True})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.opendota.com/api/players/123')
        self.assertEqual(request.get_header('User-agent'), 'DotaForge/1.0')

    @patch.dict('os.environ', {'OPENDOTA_API_KEY': 'test key'})
    @patch('apps.esports.services.opendota.urlopen')
    def test_get_json_adds_encoded_server_side_api_key(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'[]'
        urlopen.return_value = response

        OpenDotaClient().get_json('/search?q=player')

        query = parse_qs(urlparse(urlopen.call_args.args[0].full_url).query)
        self.assertEqual(query['api_key'], ['test key'])
        self.assertEqual(query['q'], ['player'])

    @patch('apps.esports.services.opendota.urlopen', side_effect=URLError('offline'))
    def test_get_json_wraps_network_errors(self, urlopen):
        with self.assertRaises(ExternalDataError):
            OpenDotaClient().get_json('/health')

    def test_search_url_encodes_query(self):
        client = OpenDotaClient()
        with patch.object(client, 'get_json', return_value=[]) as get_json:
            self.assertEqual(client.search('Pupsik & friends'), [])

        self.assertEqual(get_json.call_args.args[0], '/search?q=Pupsik+%26+friends')


class OpenDotaProfileSyncTests(TestCase):
    def setUp(self):
        self.player = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE,
            leaderboard_rank=1,
            leaderboard_name='  Top   Mid ',
            avatar_url='https://example.test/old-avatar.jpg',
        )

    def test_normalise_name_collapses_spaces_and_case(self):
        self.assertEqual(normalise_name('  TOP   Mid '), 'top mid')
        self.assertEqual(normalise_name(None), '')

    def test_resolve_account_id_requires_one_exact_name_match(self):
        client = MagicMock()
        client.search.return_value = [
            {'personaname': 'top mid', 'account_id': 123, 'avatarfull': 'https://example.test/new.jpg'},
            {'personaname': 'Top Mid Pro', 'account_id': 456},
        ]

        self.assertTrue(resolve_account_id(self.player, client))

        self.player.refresh_from_db()
        self.assertEqual(self.player.account_id, 123)
        self.assertEqual(self.player.avatar_url, 'https://example.test/new.jpg')

    def test_resolve_account_id_rejects_ambiguous_missing_and_unavailable_matches(self):
        client = MagicMock()
        client.search.return_value = [
            {'personaname': 'Top Mid', 'account_id': 123},
            {'personaname': ' top mid ', 'account_id': 456},
        ]
        self.assertFalse(resolve_account_id(self.player, client))

        client.search.return_value = [{'personaname': 'Top Mid'}]
        self.assertFalse(resolve_account_id(self.player, client))

        client.search.side_effect = ExternalDataError('offline')
        self.assertFalse(resolve_account_id(self.player, client))

        self.player.leaderboard_name = '  '
        self.assertFalse(resolve_account_id(self.player, client))

    def test_refresh_player_stats_rejects_unlinked_player(self):
        with self.assertRaises(ExternalDataError):
            refresh_player_stats(self.player, MagicMock())

    def test_refresh_player_stats_persists_profile_rank_and_record(self):
        self.player.account_id = 123
        self.player.save(update_fields=('account_id',))
        client = MagicMock()
        client.player.return_value = {
            'profile': {
                'avatarfull': 'https://example.test/player.jpg',
                'profileurl': 'https://steamcommunity.com/id/player',
                'name': 'Real Name',
                'loccountrycode': 'UA',
            },
            'rank_tier': 80,
            'leaderboard_rank': 10,
            'mmr_estimate': {'estimate': 6500},
        }
        client.win_loss.return_value = {'win': 20, 'lose': 10}

        result = refresh_player_stats(self.player, client)

        result.refresh_from_db()
        self.assertEqual(result.account_id, 123)
        self.assertEqual(result.avatar_url, 'https://example.test/player.jpg')
        self.assertEqual(result.profile_url, 'https://steamcommunity.com/id/player')
        self.assertEqual(result.real_name, 'Real Name')
        self.assertEqual(result.country_code, 'UA')
        self.assertEqual(result.rank_tier, 80)
        self.assertEqual(result.leaderboard_rank_opendota, 10)
        self.assertEqual(result.mmr_estimate, 6500)
        self.assertEqual((result.wins, result.losses), (20, 10))
        self.assertIsNotNone(result.opendota_synced_at)

    def test_refresh_player_stats_preserves_existing_values_when_profile_is_sparse(self):
        self.player.account_id = 123
        self.player.real_name = 'Previous Name'
        self.player.country_code = 'CA'
        self.player.save(update_fields=('account_id', 'real_name', 'country_code'))
        client = MagicMock()
        client.player.return_value = {'profile': {}, 'mmr_estimate': {}}
        client.win_loss.return_value = {}

        refresh_player_stats(self.player, client)
        self.player.refresh_from_db()

        self.assertEqual(self.player.avatar_url, 'https://example.test/old-avatar.jpg')
        self.assertEqual(self.player.real_name, '')
        self.assertEqual(self.player.country_code, 'CA')
        self.assertEqual((self.player.wins, self.player.losses), (0, 0))
