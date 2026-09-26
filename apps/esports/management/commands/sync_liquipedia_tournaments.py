import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from apps.esports.models import ProTeam, Tournament
from apps.esports.services.liquipedia import LiquipediaError, fetch_tournament_details, fetch_tournaments


class Command(BaseCommand):
    help = 'Import current and upcoming Dota 2 tournaments from Liquipedia.'

    def handle(self, *args, **options):
        contact = os.environ.get('LIQUIPEDIA_CONTACT_EMAIL', '').strip()
        if not contact:
            raise CommandError('Set LIQUIPEDIA_CONTACT_EMAIL so the Liquipedia API can identify this client.')
        try:
            records = fetch_tournaments(contact)
            details = fetch_tournament_details(records, contact)
        except LiquipediaError as error:
            raise CommandError(str(error)) from error
        if not records:
            raise CommandError('Liquipedia returned no current or upcoming tournament rows; existing records were kept.')

        today = timezone.localdate()
        updated = 0
        for record in records:
            from urllib.parse import unquote
            page_title = unquote(record['source_url'].split('/dota2/', 1)[-1]).replace('_', ' ')
            page_data = details.get(page_title, {})
            record['participants'] = page_data.get('participants', record['participants'])
            starts_at, ends_at = record['starts_at'], record['ends_at']
            defaults = {
                'name': record['name'],
                'starts_at': starts_at,
                'ends_at': ends_at,
                'prize_pool': record['prize_pool'],
                'source_url': record['source_url'],
                'organizer': page_data.get('organizer', ''),
                'location': page_data.get('location', ''),
                'format': page_data.get('format', ''),
                'status': 'ongoing' if starts_at <= today <= ends_at else 'upcoming',
            }
            slug = record['slug'] or slugify(record['name'])
            tournament = Tournament.objects.filter(slug=slug).first()
            if tournament and tournament.source_url and tournament.source_url != record['source_url']:
                # A slug collision must never overwrite a manually curated event.
                continue
            if tournament is None:
                tournament = Tournament(slug=slug, **defaults)
            else:
                for field, value in defaults.items():
                    setattr(tournament, field, value)
            tournament.save()
            participant_teams = []
            for team_name in record['participants']:
                team_slug = slugify(team_name)[:50] or f'team-{tournament.pk}'
                team, _ = ProTeam.objects.get_or_create(name=team_name[:100], defaults={'slug': team_slug})
                participant_teams.append(team)
            if participant_teams:
                tournament.teams.set(participant_teams)
            updated += 1
        self.stdout.write(self.style.SUCCESS(f'Synced {updated} tournaments from Liquipedia.'))
