from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ProPlayer


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

    @patch('apps.esports.views.refresh_player_stats')
    def test_detail_refreshes_stale_profile(self, refresh_player_stats):
        self.player.opendota_synced_at = timezone.now() - timedelta(hours=7)
        self.player.save()
        self.client.get(reverse('esports:pro_player_detail', args=[self.player.pk]))
        refresh_player_stats.assert_called_once_with(self.player)
