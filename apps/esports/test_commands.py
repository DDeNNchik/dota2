from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase

from .models import ProPlayer
from .services.opendota import ExternalDataError


class SyncOpenDotaProfilesCommandTests(TestCase):
    def test_resolves_refreshes_and_counts_unavailable_profiles(self):
        unresolved = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE, leaderboard_rank=1, leaderboard_name='First',
        )
        linked = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE, leaderboard_rank=2, leaderboard_name='Second', account_id=2,
        )
        no_match = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE, leaderboard_rank=3, leaderboard_name='Third',
        )
        outside_batch = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE, leaderboard_rank=4, leaderboard_name='Fourth', account_id=4,
        )
        output = StringIO()

        def resolve_if_first(player):
            if player.leaderboard_name == 'First':
                player.account_id = 1
                return True
            return False

        with (
            patch('apps.esports.management.commands.sync_opendota_profiles.resolve_account_id',
                  side_effect=resolve_if_first) as resolve,
            patch('apps.esports.management.commands.sync_opendota_profiles.refresh_player_stats',
                  side_effect=[None, ExternalDataError('offline')]) as refresh,
        ):
            call_command('sync_opendota_profiles', limit=3, stdout=output)

        self.assertEqual(resolve.call_count, 2)
        self.assertEqual(refresh.call_count, 2)
        self.assertIn('Resolved: 1; refreshed: 1; unavailable: 2.', output.getvalue())
        self.assertNotIn(outside_batch, [call.args[0] for call in refresh.call_args_list])


class SyncValveLeaderboardsCommandTests(TestCase):
    @patch('apps.esports.management.commands.sync_valve_leaderboards.sync_leaderboard', return_value=7)
    def test_syncs_each_region_and_passes_no_resolve_option(self, sync):
        output = StringIO()

        call_command('sync_valve_leaderboards', limit=7, no_resolve=True, stdout=output)

        self.assertEqual(sync.call_count, len(ProPlayer.Region.values))
        self.assertEqual(sync.call_args_list[0].kwargs, {'limit': 7, 'resolve': False})
        self.assertEqual(output.getvalue().count('leaderboard entries updated'), len(ProPlayer.Region.values))

    def test_rejects_invalid_limit_and_wraps_provider_error(self):
        with self.assertRaises(CommandError):
            call_command('sync_valve_leaderboards', limit=101)

        with patch(
            'apps.esports.management.commands.sync_valve_leaderboards.sync_leaderboard',
            side_effect=ExternalDataError('offline'),
        ):
            with self.assertRaisesRegex(CommandError, 'europe: offline'):
                call_command('sync_valve_leaderboards', region='europe', limit=5)
