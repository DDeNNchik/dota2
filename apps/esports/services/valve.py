"""Adapter for Valve's public Dota 2 regional leaderboard endpoint."""

import json
from datetime import datetime, timezone as datetime_timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction

from apps.esports.models import ProPlayer
from .opendota import ExternalDataError, resolve_account_id


class ValveLeaderboardClient:
    base_url = 'https://www.dota2.com/webapi/ILeaderboard/GetDivisionLeaderboard/v0001'
    timeout_seconds = 15

    def division(self, region):
        request = Request(
            f'{self.base_url}?division={region}&leaderboard=0',
            headers={'User-Agent': 'DotaForge/1.0'},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ExternalDataError('Valve leaderboard request failed') from error
        if not isinstance(payload.get('leaderboard'), list):
            raise ExternalDataError('Valve returned no leaderboard')
        return payload


def parse_timestamp(value):
    try:
        return datetime.fromtimestamp(int(value), tz=datetime_timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def sync_leaderboard(region, limit=100, resolve=False, client=None):
    """Store a regional Valve top list without making the page depend on API uptime."""
    client = client or ValveLeaderboardClient()
    payload = client.division(region)
    entries = payload['leaderboard'][:limit]
    source_updated_at = parse_timestamp(payload.get('time_posted'))
    synced = []

    with transaction.atomic():
        for rank, entry in enumerate(entries, start=1):
            leaderboard_name = (entry.get('name') or '')[:128]
            player, created = ProPlayer.objects.get_or_create(
                region=region,
                leaderboard_rank=rank,
                defaults={
                    'leaderboard_name': leaderboard_name,
                    'team_tag': (entry.get('team_tag') or '')[:32],
                    'sponsor': (entry.get('sponsor') or '')[:64],
                    'country_code': (entry.get('country') or '')[:2].upper(),
                    'source_updated_at': source_updated_at,
                },
            )
            if not created:
                # A leaderboard position is not a player identity.  When its
                # occupant changes, discard the old OpenDota link and cached
                # statistics before publishing the new Valve entry.
                identity_changed = player.leaderboard_name != leaderboard_name
                player.leaderboard_name = leaderboard_name
                player.team_tag = (entry.get('team_tag') or '')[:32]
                player.sponsor = (entry.get('sponsor') or '')[:64]
                player.country_code = (entry.get('country') or '')[:2].upper()
                player.source_updated_at = source_updated_at
                if identity_changed:
                    player.account_id = None
                    player.avatar_url = ''
                    player.profile_url = ''
                    player.real_name = ''
                    player.rank_tier = None
                    player.leaderboard_rank_opendota = None
                    player.mmr_estimate = None
                    player.wins = 0
                    player.losses = 0
                    player.opendota_synced_at = None
                player.save()
            synced.append(player)
        ProPlayer.objects.filter(region=region, leaderboard_rank__gt=len(entries)).delete()

    if resolve:
        for player in synced:
            if not player.account_id:
                resolve_account_id(player)
    return len(synced)
