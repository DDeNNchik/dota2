from django.contrib import admin

from .models import Hero, Profile, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('position', 'name')
    ordering = ('position',)


@admin.register(Hero)
class HeroAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'dota_nickname', 'mmr', 'country', 'microphone_available', 'updated_at')
    list_filter = ('country', 'microphone_available')
    search_fields = ('user__username', 'user__email', 'dota_nickname', 'steam_id')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('preferred_roles', 'favorite_heroes')
