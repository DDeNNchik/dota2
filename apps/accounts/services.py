"""Steam OpenID verification and cached OpenDota statistics for site users."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.utils import timezone


STEAM_OPENID_ENDPOINT = 'https://steamcommunity.com/openid/login'
STEAM_ID64_OFFSET = 76561197960265728


class SteamServiceError(RuntimeError):
    pass


def steam_openid_url(return_to, realm):
    parameters = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.mode': 'checkid_setup',
        'openid.return_to': return_to,
        'openid.realm': realm,
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
    }
    return f'{STEAM_OPENID_ENDPOINT}?{urlencode(parameters)}'


def verify_steam_response(parameters):
    """Verify Steam's signed OpenID assertion and return the SteamID64."""
    claimed_id = parameters.get('openid.claimed_id', '')
    prefix = 'https://steamcommunity.com/openid/id/'
    if not claimed_id.startswith(prefix):
        raise SteamServiceError('Steam returned an invalid identity.')
    try:
        steam_id = int(claimed_id.removeprefix(prefix))
    except ValueError as error:
        raise SteamServiceError('Steam returned an invalid identity.') from error
    if steam_id <= STEAM_ID64_OFFSET:
        raise SteamServiceError('Steam returned an invalid identity.')

    verification = {key: parameters.getlist(key) for key in parameters if key.startswith('openid.')}
    verification['openid.mode'] = 'check_authentication'
    request = Request(
        STEAM_OPENID_ENDPOINT,
        data=urlencode(verification, doseq=True).encode(),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )
    try:
        with urlopen(request, timeout=10) as response:
            verified = response.read().decode('utf-8', errors='replace')
    except (HTTPError, URLError, TimeoutError) as error:
        raise SteamServiceError('Steam could not verify the sign-in response.') from error
    if 'is_valid:true' not in verified:
        raise SteamServiceError('Steam did not verify the sign-in response.')
    return steam_id


def refresh_dota_statistics(steam_account):
    """Read a bounded, cacheable set of statistics from OpenDota."""
    from apps.esports.services.opendota import ExternalDataError, OpenDotaClient

    client = OpenDotaClient()
    try:
        player = client.player(steam_account.account_id)
        win_loss = client.win_loss(steam_account.account_id)
        recent_matches = client.get_json(f'/players/{steam_account.account_id}/recentMatches')
    except ExternalDataError as error:
        raise SteamServiceError('OpenDota is temporarily unavailable.') from error

    profile = player.get('profile') or {}
    estimate = player.get('mmr_estimate') or {}
    steam_account.persona_name = profile.get('personaname') or steam_account.persona_name
    steam_account.avatar_url = profile.get('avatarfull') or steam_account.avatar_url
    steam_account.profile_url = profile.get('profileurl') or steam_account.profile_url
    steam_account.rank_tier = player.get('rank_tier')
    mmr_estimate = estimate.get('estimate')
    computed_mmr = player.get('computed_mmr')
    steam_account.mmr_estimate = mmr_estimate if mmr_estimate is not None else (
        round(computed_mmr) if isinstance(computed_mmr, (int, float)) and computed_mmr >= 0 else None
    )
    steam_account.wins = win_loss.get('win') or 0
    steam_account.losses = win_loss.get('lose') or 0
    steam_account.recent_matches = [
        {
            'match_id': match.get('match_id'),
            'kills': match.get('kills', 0),
            'deaths': match.get('deaths', 0),
            'assists': match.get('assists', 0),
            'won': bool(match.get('radiant_win')) == (match.get('player_slot', 128) < 128),
        }
        for match in recent_matches[:10]
    ] if isinstance(recent_matches, list) else []
    steam_account.match_history_available = not bool(profile.get('fh_unavailable'))
    steam_account.stats_updated_at = timezone.now()
    steam_account.save()
    return steam_account
