from datetime import timedelta

from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import ProPlayer, Tournament
from .services.opendota import ExternalDataError, refresh_player_stats, resolve_account_id
from .services.valve import sync_leaderboard


def pro_player_list(request):
    region = request.GET.get('region', ProPlayer.Region.EUROPE)
    if region not in ProPlayer.Region.values:
        region = ProPlayer.Region.EUROPE
    players = ProPlayer.objects.filter(region=region, leaderboard_rank__lte=100).order_by('leaderboard_rank')
    data_error = None
    if not players.exists():
        try:
            sync_leaderboard(region)
            players = ProPlayer.objects.filter(region=region, leaderboard_rank__lte=100).order_by('leaderboard_rank')
        except ExternalDataError:
            data_error = 'Не удалось загрузить рейтинг Valve. Попробуйте обновить страницу позже.'
    source_updated_at = players.exclude(source_updated_at__isnull=True).order_by('-source_updated_at').values_list('source_updated_at', flat=True).first()
    return render(request, 'esports/pro_player_list.html', {'players': players, 'region': region, 'regions': ProPlayer.Region.choices, 'source_updated_at': source_updated_at, 'data_error': data_error})


def pro_player_detail(request, pk):
    player = get_object_or_404(ProPlayer, pk=pk)
    data_error = None
    stale_before = timezone.now() - timedelta(hours=6)
    if not player.account_id:
        resolve_account_id(player)
    if player.account_id and (not player.opendota_synced_at or player.opendota_synced_at < stale_before):
        try:
            refresh_player_stats(player)
        except ExternalDataError:
            data_error = 'OpenDota временно недоступен. Показаны последние сохранённые данные.'
    return render(request, 'esports/pro_player_detail.html', {'player': player, 'data_error': data_error})


def tournament_list(request):
    return render(request, 'esports/tournament_list.html', {'tournaments': Tournament.objects.prefetch_related('teams')})


def tournament_detail(request, slug):
    tournament = get_object_or_404(Tournament.objects.prefetch_related('teams'), slug=slug)
    return render(request, 'esports/tournament_detail.html', {'tournament': tournament})
