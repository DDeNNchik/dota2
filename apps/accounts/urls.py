from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.DotaForgeLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('steam/connect/', views.steam_connect, name='steam_connect'),
    path('steam/callback/', views.steam_callback, name='steam_callback'),
    path('steam/stats/', views.steam_stats, name='steam_stats'),
    path('steam/refresh/', views.steam_refresh, name='steam_refresh'),
    path('steam/disconnect/', views.steam_disconnect, name='steam_disconnect'),
]
