from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import SteamAccount
from apps.accounts.services import SteamServiceError, refresh_dota_statistics


class Command(BaseCommand):
    help = 'Refresh cached OpenDota statistics for connected Steam accounts.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=25)
        parser.add_argument('--stale-hours', type=int, default=6)

    def handle(self, *args, **options):
        limit = max(1, options['limit'])
        stale_before = timezone.now() - timedelta(hours=max(1, options['stale_hours']))
        accounts = SteamAccount.objects.filter(
            Q(stats_updated_at__isnull=True) | Q(stats_updated_at__lt=stale_before)
        ).order_by('stats_updated_at')[:limit]
        updated = unavailable = 0
        for account in accounts:
            try:
                refresh_dota_statistics(account)
                updated += 1
            except SteamServiceError:
                unavailable += 1
        self.stdout.write(self.style.SUCCESS(f'Updated: {updated}; unavailable: {unavailable}.'))
