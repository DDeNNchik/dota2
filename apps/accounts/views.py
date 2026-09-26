from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from secrets import token_urlsafe

from .forms import ProfileForm, RegistrationForm
from .models import Profile, SteamAccount
from .services import STEAM_ID64_OFFSET, SteamServiceError, refresh_dota_statistics, steam_openid_url, verify_steam_response


User = get_user_model()


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
