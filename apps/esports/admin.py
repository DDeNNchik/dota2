from django.contrib import admin

from .models import ProPlayer, ProTeam, ProTeamMember, Tournament


@admin.register(ProTeam)
class ProTeamAdmin(admin.ModelAdmin):
    list_display = ('ranking_position', 'name', 'short_name', 'region', 'rating', 'source_url')
    list_filter = ('region',)
    search_fields = ('name', 'short_name')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ProTeamMember)
class ProTeamMemberAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'team', 'role', 'real_name')
    list_filter = ('team',)
    search_fields = ('nickname', 'real_name', 'team__name')


@admin.register(ProPlayer)
class ProPlayerAdmin(admin.ModelAdmin):
    list_display = ('leaderboard_name', 'region', 'leaderboard_rank', 'account_id', 'rank_tier', 'opendota_synced_at')
    list_filter = ('region', 'rank_tier')
    search_fields = ('leaderboard_name', 'team_tag', 'real_name', 'account_id')
    readonly_fields = ('source_updated_at', 'opendota_synced_at', 'last_seen_at')


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'starts_at', 'ends_at', 'prize_pool', 'location')
    list_filter = ('status', 'starts_at')
    search_fields = ('name', 'organizer', 'location')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('teams',)
