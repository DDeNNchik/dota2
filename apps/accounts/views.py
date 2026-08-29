from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProfileForm, RegistrationForm
from .models import Profile


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
    return render(request, 'accounts/profile_detail.html', {'profile_user': user, 'profile': profile})
