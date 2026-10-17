from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from secrets import token_urlsafe
import re

from .forms import ProfileForm, RegistrationForm
from .models import Profile, SteamAccount
from .services import STEAM_ID64_OFFSET, SteamServiceError, refresh_dota_statistics, steam_openid_url, verify_steam_response


User = get_user_model()


def player_search(request):
    """Search profiles registered on DotaForge, without contacting external services."""
    query = ' '.join(request.GET.get('q', '').split())[:80]
    if len(query) < 2:
        return JsonResponse({'results': []})

    results = []
    players = User.objects.filter(profile__isnull=False).filter(
        Q(username__icontains=query)
        | Q(profile__dota_nickname__icontains=query)
        | Q(steam_account__persona_name__icontains=query)
    ).select_related('profile', 'steam_account').order_by('username')[:8]

    for player in players:
        try:
            steam_account = player.steam_account
        except SteamAccount.DoesNotExist:
            steam_account = None
        nickname = player.profile.dota_nickname or (steam_account.persona_name if steam_account else '') or player.username
        avatar_url = ''
        if steam_account and steam_account.avatar_url:
            avatar_url = steam_account.avatar_url
        elif player.profile.avatar:
            avatar_url = request.build_absolute_uri(player.profile.avatar.url)
        results.append({
            'nickname': nickname,
            'username': player.username,
            'avatar_url': avatar_url,
            'url': reverse('profile_detail', kwargs={'username': player.username}),
        })
    return JsonResponse({'results': results})


def site_players(request):
    players = User.objects.filter(
        steam_account__mmr_estimate__isnull=False,
    ).select_related('profile', 'steam_account').order_by('-steam_account__mmr_estimate', 'username')[:100]
    return render(request, 'players/site_players.html', {'players': players})


def _profile_match_score(profile, mmr, candidate, candidate_mmr):
    """Score a potential teammate using only profile data both players supplied."""
    score = 0
    reasons = []
    roles = set(profile.preferred_roles.values_list('position', flat=True))
    candidate_roles = set(candidate.preferred_roles.values_list('position', flat=True))
    if roles and candidate_roles:
        if roles.isdisjoint(candidate_roles):
            score += 25
            reasons.append('Роли дополняют друг друга')
        else:
            score += 12
            reasons.append('Совпадают игровые роли')

    if mmr and candidate_mmr:
        difference = abs(mmr - candidate_mmr)
        score += max(0, 30 - difference // 100)
        if difference <= 2000:
            reasons.append('Похожий MMR')

    if profile.timezone and candidate.timezone:
        own_offset = int(profile.timezone.removeprefix('GMT'))
        other_offset = int(candidate.timezone.removeprefix('GMT'))
        difference = abs(own_offset - other_offset)
        points = max(0, 15 - difference * 5)
        score += points
        if points:
            reasons.append('Похожий часовой пояс')

    heroes = set(profile.favorite_heroes.values_list('pk', flat=True))
    candidate_heroes = set(candidate.favorite_heroes.values_list('pk', flat=True))
    if heroes and candidate_heroes:
        shared = len(heroes & candidate_heroes)
        if shared:
            score += round(15 * shared / min(len(heroes), len(candidate_heroes)))
            reasons.append('Есть общие любимые герои')

    if profile.microphone_available and candidate.microphone_available:
        score += 5
        reasons.append('У обоих есть микрофон')

    if profile.country and candidate.country and profile.country.strip().casefold() == candidate.country.strip().casefold():
        score += 5
        reasons.append('Одна страна')

    own_times = set(re.findall(r'[\w:]+', profile.availability.casefold()))
    candidate_times = set(re.findall(r'[\w:]+', candidate.availability.casefold()))
    if own_times and candidate_times:
        shared_times = len(own_times & candidate_times)
        if shared_times:
            score += round(5 * shared_times / len(own_times | candidate_times))
            reasons.append('Похожее расписание')

    return score, reasons


@login_required
def team_finder(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    matches = None
    has_search_data = bool(
        profile.preferred_roles.exists()
        or profile.favorite_heroes.exists()
        or profile.timezone
        or profile.country
        or profile.availability
        or profile.microphone_available
        or profile.mmr
        or SteamAccount.objects.filter(user=request.user, mmr_estimate__isnull=False).exists()
    )

    if request.method == 'POST':
        own_mmr = profile.mmr or getattr(getattr(request.user, 'steam_account', None), 'mmr_estimate', None)
        candidates = User.objects.filter(profile__isnull=False).exclude(pk=request.user.pk).select_related(
            'profile', 'steam_account'
        ).prefetch_related('profile__preferred_roles', 'profile__favorite_heroes').order_by('username')
        matches = []
        for candidate_user in candidates:
            candidate = candidate_user.profile
            candidate_mmr = candidate.mmr or getattr(getattr(candidate_user, 'steam_account', None), 'mmr_estimate', None)
            score, reasons = _profile_match_score(profile, own_mmr, candidate, candidate_mmr)
            if not score:
                continue
            avatar_url = candidate_user.steam_account.avatar_url if hasattr(candidate_user, 'steam_account') else ''
            if not avatar_url and candidate.avatar:
                avatar_url = request.build_absolute_uri(candidate.avatar.url)
            matches.append({
                'profile': candidate,
                'username': candidate_user.username,
                'nickname': candidate.dota_nickname or (candidate_user.steam_account.persona_name if hasattr(candidate_user, 'steam_account') else '') or candidate_user.username,
                'avatar_url': avatar_url,
                'mmr': candidate_mmr,
                'score': score,
                'reasons': reasons,
                'url': reverse('profile_detail', kwargs={'username': candidate_user.username}),
            })
        matches.sort(key=lambda match: (-match['score'], match['nickname'].casefold()))
        matches = matches[:12]

    return render(request, 'players/team_finder.html', {
        'matches': matches,
        'has_search_data': has_search_data,
    })


class DotaForgeLoginView(auth_views.LoginView):
    """Keep the login endpoint unavailable once the session is authenticated."""

    template_name = 'registration/login.html'
    redirect_authenticated_user = True


def register(request):
    if request.user.is_authenticated:
        return redirect('profile_edit')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Аккаунт создан. Теперь можно заполнить игровой профиль.')
        return redirect('profile_edit')
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile_edit(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Игровой профиль сохранён.')
        return redirect('profile_detail', username=request.user.username)
    return render(request, 'accounts/profile_edit.html', {'form': form})


def profile_detail(request, username):
    user = get_object_or_404(User, username__iexact=username)
    profile, _ = Profile.objects.get_or_create(user=user)
    return render(request, 'accounts/profile_detail.html', {
        'profile_user': user,
        'profile': profile,
        'steam_account': SteamAccount.objects.filter(user=user).first(),
    })


@login_required
def steam_connect(request):
    state = token_urlsafe(24)
    callback = request.build_absolute_uri(reverse('accounts:steam_callback'))
    callback = f'{callback}?state={state}'
    request.session['steam_openid_state'] = state
    realm = request.build_absolute_uri('/')
    return redirect(steam_openid_url(callback, realm))


@login_required
def steam_callback(request):
    state = request.GET.get('state')
    expected_state = request.session.pop('steam_openid_state', None)
    if not state or state != expected_state:
        return HttpResponseBadRequest('Invalid Steam connection request.')
    try:
        steam_id = verify_steam_response(request.GET)
    except SteamServiceError as error:
        messages.error(request, str(error))
        return redirect('profile_edit')

    existing = SteamAccount.objects.filter(steam_id=steam_id).exclude(user=request.user).first()
    if existing:
        messages.error(request, 'This Steam account is already linked to another DotaForge account.')
        return redirect('profile_edit')
    account, _ = SteamAccount.objects.update_or_create(
        user=request.user,
        defaults={'steam_id': steam_id, 'account_id': steam_id - STEAM_ID64_OFFSET, 'profile_url': f'https://steamcommunity.com/profiles/{steam_id}/'},
    )
    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile.steam_id = account.profile_url
    profile.save(update_fields=('steam_id', 'updated_at'))
    try:
        refresh_dota_statistics(account)
        messages.success(request, 'Steam connected. Dota statistics were updated.')
    except SteamServiceError:
        messages.success(request, 'Steam connected. Dota statistics will be available after an OpenDota update.')
    return redirect('accounts:steam_stats')


@login_required
def steam_stats(request):
    account = get_object_or_404(SteamAccount, user=request.user)
    return render(request, 'accounts/steam_stats.html', {'steam_account': account})


@login_required
@require_POST
def steam_refresh(request):
    account = get_object_or_404(SteamAccount, user=request.user)
    try:
        refresh_dota_statistics(account)
        messages.success(request, 'Dota statistics were updated.')
    except SteamServiceError as error:
        messages.error(request, str(error))
    return redirect('accounts:steam_stats')


@login_required
@require_POST
def steam_disconnect(request):
    account = get_object_or_404(SteamAccount, user=request.user)
    account.delete()
    Profile.objects.filter(user=request.user).update(steam_id='')
    messages.success(request, 'Steam account was disconnected.')
    return redirect('profile_edit')
