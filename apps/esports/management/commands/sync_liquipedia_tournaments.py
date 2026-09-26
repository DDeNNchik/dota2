import os
from urllib.parse import quote

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from apps.esports.models import ProTeam, ProTeamMember, Tournament
from apps.esports.services.liquipedia import (
    LiquipediaError,
    fetch_team_profiles,
    fetch_team_rankings,
    fetch_tournament_details,
    fetch_tournaments,
)


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

        # Rankings update alongside the tournament schedule. Keep the previous
        # ranking if Liquipedia's separate rankings page is temporarily down.
        import time
        time.sleep(2)
        try:
            rankings = fetch_team_rankings(contact)
        except LiquipediaError as error:
            self.stderr.write(self.style.WARNING(f'Tournaments synced, but team rankings were not refreshed: {error}'))
            rankings = []
        if rankings:
            current_names = [entry['name'] for entry in rankings]
            ProTeam.objects.filter(ranking_position__isnull=False).exclude(name__in=current_names).update(ranking_position=None)

        today = timezone.localdate()
        updated = 0
        ranked_team_count = 0
        for entry in rankings:
            team = ProTeam.objects.filter(name__iexact=entry['name']).first()
            if team is None:
                team_slug = slugify(entry['name'])[:50] or f"liquipedia-team-{entry['rank']}"
                if ProTeam.objects.filter(slug=team_slug).exists():
                    team_slug = f"{team_slug[:40]}-{entry['rank']}"
                team = ProTeam(name=entry['name'][:100], slug=team_slug)
            team.ranking_position = entry['rank']
            team.rating = entry['rating']
            team.region = entry['region'][:80]
            team.source_url = entry['source_url']
            if not team.logo_url and entry['logo_url']:
                team.logo_url = entry['logo_url']
            team.save()
            ranked_team_count += 1

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
                team = ProTeam.objects.filter(name__iexact=team_name[:100]).first()
                if team is None:
                    if ProTeam.objects.filter(slug=team_slug).exists():
                        team_slug = f'{team_slug[:40]}-{tournament.pk}'
                    team = ProTeam.objects.create(name=team_name[:100], slug=team_slug)
                participant_teams.append(team)
            if participant_teams:
                tournament.teams.set(participant_teams)
            updated += 1

        tournament_teams = ProTeam.objects.filter(tournaments__source_url__contains='liquipedia.net').distinct()
        teams = list({team.pk: team for team in list(tournament_teams) + list(
            ProTeam.objects.filter(ranking_position__isnull=False)
        )}.values())
        try:
            profiles = fetch_team_profiles(teams, contact)
        except LiquipediaError as error:
            self.stderr.write(self.style.WARNING(f'Tournaments synced, but team profiles were not refreshed: {error}'))
            profiles = {}
        profiles_by_name = {name.casefold(): profile for name, profile in profiles.items()}
        roster_count = logo_count = 0
        for team in teams:
            profile = profiles_by_name.get(team.name.casefold())
            if not profile:
                continue
            if profile['logo_url']:
                team.logo_url = profile['logo_url']
                logo_count += 1
            if profile['source_url']:
                team.source_url = profile['source_url']
            team.save(update_fields=('logo_url', 'source_url'))
            roster = profile['roster']
            if roster:
                active_nicknames = []
                for member in roster:
                    active_nicknames.append(member['nickname'])
                    player_url = f"https://liquipedia.net/dota2/{quote(member['title'].replace(' ', '_'), safe='/()_')}"
                    ProTeamMember.objects.update_or_create(
                        team=team,
                        nickname=member['nickname'],
                        defaults={
                            'real_name': member['real_name'],
                            'role': member['role'],
                            'photo_url': member.get('photo_url', ''),
                            'source_url': player_url,
                            'sort_order': member['sort_order'],
                        },
                    )
                team.roster.exclude(nickname__in=active_nicknames).delete()
                roster_count += len(active_nicknames)
        self.stdout.write(self.style.SUCCESS(
            f'Synced {updated} tournaments and {ranked_team_count} ranked teams, '
            f'{logo_count} team logos and {roster_count} active roster entries from Liquipedia.'
        ))
