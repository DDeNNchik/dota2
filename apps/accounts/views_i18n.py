from django.conf import settings
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def set_language(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    language = request.POST.get('language')
    redirect_to = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    if not url_has_allowed_host_and_scheme(redirect_to, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        redirect_to = '/'
    response = redirect(redirect_to)
    if language in dict(settings.LANGUAGES):
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language, max_age=60 * 60 * 24 * 365, samesite='Lax')
    return response
