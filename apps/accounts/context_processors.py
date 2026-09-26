from .models import Profile, SteamAccount


def current_profile(request):
    """Expose a guaranteed profile to shared templates for signed-in users."""
    if not request.user.is_authenticated:
        return {}

    profile, _ = Profile.objects.get_or_create(user=request.user)
    steam_account = SteamAccount.objects.filter(user=request.user).first()
    return {'current_profile': profile, 'current_steam_account': steam_account}
