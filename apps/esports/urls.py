from django.urls import path

from . import views

app_name = 'esports'

urlpatterns = [
    path('players/', views.pro_player_list, name='pro_player_list'),
    path('players/<int:pk>/', views.pro_player_detail, name='pro_player_detail'),
    path('tournaments/', views.tournament_list, name='tournament_list'),
    path('tournaments/<slug:slug>/', views.tournament_detail, name='tournament_detail'),
    path('teams/', views.pro_team_list, name='pro_team_list'),
    path('teams/<slug:slug>/', views.pro_team_detail, name='pro_team_detail'),
]
