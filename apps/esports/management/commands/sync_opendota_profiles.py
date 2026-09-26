from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.esports.models import ProPlayer
from apps.esports.services.opendota import ExternalDataError, refresh_player_stats, resolve_account_id


class Command(BaseCommand):
    help = 'Resolve Valve entries and refresh a bounded batch of OpenDota player profiles.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=25)
        parser.add_argument('--stale-hours', type=int, default=6)

    def handle(self, *args, **options):
        limit = max(1, options['limit'])
        stale_before = timezone.now() - timedelta(hours=max(1, options['stale_hours']))
        entries = list(ProPlayer.objects.filter(leaderboard_rank__lte=100).filter(
            Q(opendota_synced_at__isnull=True) | Q(opendota_synced_at__lt=stale_before)
        ).order_by('opendota_synced_at', 'region', 'leaderboard_rank')[:limit])
        refreshed = resolved = unavailable = 0
        for player in entries:
            if not player.account_id and resolve_account_id(player):
                resolved += 1
            if not player.account_id:
                unavailable += 1
                continue
            try:
                refresh_player_stats(player)
                refreshed += 1
            except ExternalDataError:
                unavailable += 1
        self.stdout.write(self.style.SUCCESS(f'Resolved: {resolved}; refreshed: {refreshed}; unavailable: {unavailable}.'))
