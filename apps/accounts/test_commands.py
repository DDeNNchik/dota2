from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import SteamAccount
from .services import STEAM_ID64_OFFSET, SteamServiceError


User = get_user_model()


class SyncSteamStatisticsCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sync_user', password='testpass')

    @patch('apps.accounts.management.commands.sync_steam_statistics.refresh_dota_statistics')
    def test_refreshes_only_accounts_with_missing_or_stale_stats(self, refresh):
        stale = SteamAccount.objects.create(
            user=self.user,
            steam_id=STEAM_ID64_OFFSET + 1,
            account_id=1,
            stats_updated_at=timezone.now() - timedelta(hours=8),
        )
        fresh_user = User.objects.create_user(username='fresh_user', password='testpass')
        SteamAccount.objects.create(
            user=fresh_user,
            steam_id=STEAM_ID64_OFFSET + 2,
            account_id=2,
            stats_updated_at=timezone.now(),
        )
        missing_user = User.objects.create_user(username='missing_stats', password='testpass')
        missing = SteamAccount.objects.create(
            user=missing_user,
            steam_id=STEAM_ID64_OFFSET + 3,
            account_id=3,
        )
        output = StringIO()

        call_command('sync_steam_statistics', stale_hours=6, stdout=output)

        self.assertCountEqual([call.args[0] for call in refresh.call_args_list], [stale, missing])
        self.assertIn('Updated: 2; unavailable: 0.', output.getvalue())

    @patch('apps.accounts.management.commands.sync_steam_statistics.refresh_dota_statistics', side_effect=SteamServiceError)
    def test_reports_provider_failures_and_clamps_nonpositive_limit(self, refresh):
        account = SteamAccount.objects.create(
            user=self.user,
            steam_id=STEAM_ID64_OFFSET + 4,
            account_id=4,
        )
        output = StringIO()

        call_command('sync_steam_statistics', limit=0, stale_hours=0, stdout=output)

        refresh.assert_called_once_with(account)
        self.assertIn('Updated: 0; unavailable: 1.', output.getvalue())
