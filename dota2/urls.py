"""
URL configuration for dota2 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.shortcuts import render
from django.views.generic import TemplateView

from apps.accounts import views as account_views
from apps.accounts.views_i18n import set_language
from apps.esports.services.news import fetch_homepage_news, translate_homepage_news


def home(request):
    news = translate_homepage_news(fetch_homepage_news(), request.LANGUAGE_CODE)
    return render(request, 'home.html', {'news': news})


def news_page(request):
    news = translate_homepage_news(fetch_homepage_news(), request.LANGUAGE_CODE)
    return render(request, 'news.html', {'news': news})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('news/', news_page, name='news'),
    path('players/search/', account_views.player_search, name='player_search'),
    path('players/site/', account_views.site_players, name='site_players'),
    path('players/find-team/', account_views.team_finder, name='team_finder'),
    path('players/', TemplateView.as_view(template_name='players/hub.html'), name='players_hub'),
    path('accounts/', include('apps.accounts.urls')),
    path('language/set/', set_language, name='set_language'),
    path('pro/', include('apps.esports.urls')),
    path('profile/edit/', account_views.profile_edit, name='profile_edit'),
    path('profile/<str:username>/', account_views.profile_detail, name='profile_detail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
