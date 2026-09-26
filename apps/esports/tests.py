from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ProPlayer
from .services.valve import sync_leaderboard


class StubValveClient:
    def __init__(self, entries):
        self.entries = entries

    def division(self, region):
        return {'leaderboard': self.entries, 'time_posted': 1_700_000_000}


class LeaderboardSyncTests(TestCase):
    def test_player_change_in_a_rank_slot_clears_old_opendota_data(self):
        old_player = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE,
            leaderboard_rank=1,
            leaderboard_name='Old Player',
            account_id=42,
            avatar_url='https://example.test/avatar.jpg',
            rank_tier=80,
            wins=10,
            losses=5,
            opendota_synced_at=timezone.now(),
        )

        sync_leaderboard(
            ProPlayer.Region.EUROPE,
            limit=1,
            client=StubValveClient([{'name': 'New Player', 'country': 'ua'}]),
        )

        old_player.refresh_from_db()
        self.assertEqual(old_player.leaderboard_name, 'New Player')
        self.assertIsNone(old_player.account_id)
        self.assertEqual(old_player.avatar_url, '')
        self.assertIsNone(old_player.rank_tier)
        self.assertEqual(old_player.wins, 0)
        self.assertEqual(old_player.losses, 0)
        self.assertIsNone(old_player.opendota_synced_at)


class LeaderboardViewsTests(TestCase):
    def setUp(self):
        self.player = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE,
            leaderboard_rank=1,
            leaderboard_name='Top Mid',
            account_id=123,
            rank_tier=80,
            wins=18,
            losses=12,
            opendota_synced_at=timezone.now(),
        )

    def test_list_displays_the_selected_valve_region(self):
        response = self.client.get(reverse('esports:pro_player_list'), {'region': 'europe'})
        self.assertContains(response, 'Top Mid')
        self.assertContains(response, '#1')

    def test_detail_displays_cached_opendota_statistics(self):
        response = self.client.get(reverse('esports:pro_player_detail', args=[self.player.pk]))
        self.assertContains(response, '60.0%')
        self.assertContains(response, 'Immortal')

    def test_detail_uses_cached_profile_without_external_sync(self):
        response = self.client.get(reverse('esports:pro_player_detail', args=[self.player.pk]))
        self.assertEqual(response.status_code, 200)

    def test_unlinked_player_has_clear_status_instead_of_syncing(self):
        player = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE,
            leaderboard_rank=2,
            leaderboard_name='Unlinked Player',
        )
        response = self.client.get(reverse('esports:pro_player_detail', args=[player.pk]))
        self.assertContains(response, 'Statistics are not available yet')
