from django.core.management.base import BaseCommand, CommandError

from apps.esports.models import ProPlayer
from apps.esports.services.opendota import ExternalDataError
from apps.esports.services.valve import sync_leaderboard


class Command(BaseCommand):
    help = 'Synchronise Valve regional top-100 leaderboards.'

    def add_arguments(self, parser):
        parser.add_argument('--region', choices=(*ProPlayer.Region.values, 'all'), default='all')
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--resolve', action='store_true', help='Try exact OpenDota account-name matches for new entries.')

    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 100:
            raise CommandError('--limit must be between 1 and 100.')
        regions = ProPlayer.Region.values if options['region'] == 'all' else (options['region'],)
        for region in regions:
            try:
                count = sync_leaderboard(region, limit=limit, resolve=options['resolve'])
            except ExternalDataError as error:
                raise CommandError(f'{region}: {error}') from error
            self.stdout.write(self.style.SUCCESS(f'{region}: {count} leaderboard entries updated.'))
