"""Small, dependency-free client for the public OpenDota API."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.utils import timezone


class ExternalDataError(RuntimeError):
    """The remote provider did not return usable data."""


class OpenDotaClient:
    base_url = 'https://api.opendota.com/api'
    timeout_seconds = 12

    def get_json(self, path):
        request = Request(f'{self.base_url}{path}', headers={'User-Agent': 'DotaForge/1.0'})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ExternalDataError('OpenDota request failed') from error

    def search(self, name):
        return self.get_json(f'/search?q={quote(name)}')

    def player(self, account_id):
        return self.get_json(f'/players/{account_id}')

    def win_loss(self, account_id):
        return self.get_json(f'/players/{account_id}/wl')


def normalise_name(value):
    return ' '.join((value or '').casefold().split())


def resolve_account_id(player, client=None):
    """Attach an account only when OpenDota supplies an exact name match.

    Valve's public leaderboard does not include account IDs, so fuzzy matching
    would risk displaying another player's statistics.
    """
    client = client or OpenDotaClient()
    target = normalise_name(player.leaderboard_name)
    if not target:
        return False
    try:
        candidates = client.search(player.leaderboard_name)
    except ExternalDataError:
        return False
    exact_matches = [candidate for candidate in candidates if normalise_name(candidate.get('personaname')) == target]
    if len(exact_matches) != 1 or not exact_matches[0].get('account_id'):
        return False
    player.account_id = exact_matches[0]['account_id']
    player.avatar_url = exact_matches[0].get('avatarfull') or player.avatar_url
    player.save(update_fields=('account_id', 'avatar_url'))
    return True


def refresh_player_stats(player, client=None):
    """Refresh one already-resolved Valve leaderboard entry from OpenDota."""
    if not player.account_id:
        raise ExternalDataError('No OpenDota account ID is linked')
    client = client or OpenDotaClient()
    player_data = client.player(player.account_id)
    win_loss = client.win_loss(player.account_id)
    profile = player_data.get('profile') or {}
    estimate = player_data.get('mmr_estimate') or {}

    player.avatar_url = profile.get('avatarfull') or player.avatar_url
    player.profile_url = profile.get('profileurl') or player.profile_url
    player.real_name = profile.get('name') or ''
    player.country_code = profile.get('loccountrycode') or player.country_code
    player.rank_tier = player_data.get('rank_tier')
    player.leaderboard_rank_opendota = player_data.get('leaderboard_rank')
    player.mmr_estimate = estimate.get('estimate')
    player.wins = win_loss.get('win') or 0
    player.losses = win_loss.get('lose') or 0
    player.opendota_synced_at = timezone.now()
    player.save(update_fields=(
        'avatar_url', 'profile_url', 'real_name', 'country_code', 'rank_tier',
        'leaderboard_rank_opendota', 'mmr_estimate', 'wins', 'losses', 'opendota_synced_at',
    ))
    return player
