from .models import Profile


def current_profile(request):
    """Expose a guaranteed profile to shared templates for signed-in users."""
    if not request.user.is_authenticated:
        return {}

    profile, _ = Profile.objects.get_or_create(user=request.user)
    return {'current_profile': profile}
