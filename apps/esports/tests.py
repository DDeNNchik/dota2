from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ProPlayer
from .services.opendota import ExternalDataError
from .services.valve import sync_leaderboard


class StubValveClient:
    def __init__(self, entries, time_posted=1_700_000_000):
        self.entries = entries
        self.time_posted = time_posted
        self.requested_region = None

    def division(self, region):
        self.requested_region = region
        return {'leaderboard': self.entries, 'time_posted': self.time_posted}


class LeaderboardSyncTests(TestCase):
    def test_player_change_in_a_rank_slot_clears_cached_opendota_data(self):
        player = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE,
            leaderboard_rank=1,
            leaderboard_name='Old Player',
            team_tag='OLD',
            sponsor='Old sponsor',
            country_code='US',
            account_id=42,
            avatar_url='https://example.test/avatar.jpg',
            profile_url='https://example.test/profile',
            real_name='Old Real Name',
            rank_tier=80,
            leaderboard_rank_opendota=1,
            mmr_estimate=9000,
            wins=10,
            losses=5,
            opendota_synced_at=timezone.now(),
        )

        sync_leaderboard(
            ProPlayer.Region.EUROPE,
            limit=1,
            client=StubValveClient([{
                'name': 'New Player', 'team_tag': 'NEW', 'sponsor': 'New sponsor', 'country': 'ua',
            }]),
        )

        player.refresh_from_db()
        self.assertEqual(player.leaderboard_name, 'New Player')
        self.assertEqual(player.team_tag, 'NEW')
        self.assertEqual(player.sponsor, 'New sponsor')
        self.assertEqual(player.country_code, 'UA')
        self.assertIsNone(player.account_id)
        self.assertEqual(player.avatar_url, '')
        self.assertEqual(player.profile_url, '')
        self.assertEqual(player.real_name, '')
        self.assertIsNone(player.rank_tier)
        self.assertIsNone(player.leaderboard_rank_opendota)
        self.assertIsNone(player.mmr_estimate)
        self.assertEqual(player.wins, 0)
        self.assertEqual(player.losses, 0)
        self.assertIsNone(player.opendota_synced_at)

    def test_same_player_keeps_cached_stats_and_updates_valve_fields(self):
        player = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE,
            leaderboard_rank=1,
            leaderboard_name='Same Player',
            account_id=42,
            rank_tier=80,
            wins=10,
            losses=5,
            opendota_synced_at=timezone.now(),
        )
        synced_at = player.opendota_synced_at
        client = StubValveClient([{'name': 'Same Player', 'team_tag': 'TEAM', 'country': 'ua'}])

        count = sync_leaderboard(ProPlayer.Region.EUROPE, limit=1, client=client)

        player.refresh_from_db()
        self.assertEqual(count, 1)
        self.assertEqual(client.requested_region, ProPlayer.Region.EUROPE)
        self.assertEqual(player.account_id, 42)
        self.assertEqual(player.rank_tier, 80)
        self.assertEqual((player.wins, player.losses), (10, 5))
        self.assertEqual(player.opendota_synced_at, synced_at)
        self.assertEqual(player.team_tag, 'TEAM')
        self.assertEqual(player.country_code, 'UA')
        self.assertIsNotNone(player.source_updated_at)

    def test_sync_deletes_rank_slots_missing_from_new_leaderboard(self):
        first = ProPlayer.objects.create(region=ProPlayer.Region.EUROPE, leaderboard_rank=1, leaderboard_name='First')
        second = ProPlayer.objects.create(region=ProPlayer.Region.EUROPE, leaderboard_rank=2, leaderboard_name='Second')
        other_region = ProPlayer.objects.create(region=ProPlayer.Region.CHINA, leaderboard_rank=2, leaderboard_name='China')

        sync_leaderboard(ProPlayer.Region.EUROPE, client=StubValveClient([{'name': 'First'}]))

        self.assertTrue(ProPlayer.objects.filter(pk=first.pk).exists())
        self.assertFalse(ProPlayer.objects.filter(pk=second.pk).exists())
        self.assertTrue(ProPlayer.objects.filter(pk=other_region.pk).exists())


class LeaderboardViewsTests(TestCase):
    def setUp(self):
        self.player = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE,
            leaderboard_rank=1,
            leaderboard_name='Top Mid',
            account_id=123,
            rank_tier=80,
            leaderboard_rank_opendota=45,
            mmr_estimate=9000,
            wins=18,
            losses=12,
            opendota_synced_at=timezone.now(),
        )

    def test_list_displays_cached_player_in_selected_region(self):
        response = self.client.get(reverse('esports:pro_player_list'), {'region': 'europe'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['region'], ProPlayer.Region.EUROPE)
        self.assertContains(response, 'Top Mid')
        self.assertContains(response, '#1')

    def test_list_falls_back_to_europe_for_an_invalid_region(self):
        response = self.client.get(reverse('esports:pro_player_list'), {'region': 'unknown'})

        self.assertEqual(response.context['region'], ProPlayer.Region.EUROPE)
        self.assertContains(response, 'Top Mid')

    def test_list_shows_only_top_100(self):
        ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE,
            leaderboard_rank=101,
            leaderboard_name='Outside Top 100',
        )

        response = self.client.get(reverse('esports:pro_player_list'), {'region': 'europe'})

        self.assertContains(response, 'Top Mid')
        self.assertNotContains(response, 'Outside Top 100')

    @patch('apps.esports.views.sync_leaderboard', side_effect=ExternalDataError('Valve unavailable'))
    def test_empty_list_reports_provider_error_without_crashing(self, sync):
        response = self.client.get(reverse('esports:pro_player_list'), {'region': 'china'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Не удалось загрузить рейтинг Valve')
        sync.assert_called_once_with(ProPlayer.Region.CHINA)

    def test_detail_displays_cached_opendota_statistics(self):
        response = self.client.get(reverse('esports:pro_player_detail', args=[self.player.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '60.0%')
        self.assertContains(response, 'Immortal')
        self.assertContains(response, '9000')
        self.assertContains(response, '#45')

    @patch('apps.esports.services.opendota.urlopen')
    def test_detail_uses_cached_profile_without_external_request(self, urlopen):
        response = self.client.get(reverse('esports:pro_player_detail', args=[self.player.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Top Mid')
        urlopen.assert_not_called()

    def test_unlinked_player_shows_clear_unavailable_status(self):
        player = ProPlayer.objects.create(
            region=ProPlayer.Region.EUROPE,
            leaderboard_rank=2,
            leaderboard_name='Unlinked Player',
        )

        response = self.client.get(reverse('esports:pro_player_detail', args=[player.pk]))

        self.assertContains(response, 'Statistics are not available yet')
        self.assertNotContains(response, 'OpenDota rank')
