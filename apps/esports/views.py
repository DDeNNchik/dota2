from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import ProPlayer, Tournament
from .services.opendota import ExternalDataError
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
    # Network requests do not belong to a page view: OpenDota can be slow or
    # unavailable, and a click must always render the locally cached card.
    # The sync_opendota_profiles command refreshes this data in the background.
    return render(request, 'esports/pro_player_detail.html', {'player': player})


def tournament_list(request):
    tournaments = Tournament.objects.filter(ends_at__gte=timezone.localdate()).exclude(status=Tournament.Status.COMPLETED).prefetch_related('teams')
    return render(request, 'esports/tournament_list.html', {'tournaments': tournaments})


def tournament_detail(request, slug):
    tournament = get_object_or_404(Tournament.objects.prefetch_related('teams'), slug=slug)
    return render(request, 'esports/tournament_detail.html', {'tournament': tournament})
