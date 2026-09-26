from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0006_replace_timezones_with_gmt_offsets')]

    operations = [
        migrations.CreateModel(
            name='SteamAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('steam_id', models.PositiveBigIntegerField(unique=True, verbose_name='SteamID64')),
                ('account_id', models.PositiveBigIntegerField(unique=True, verbose_name='Dota account ID')),
                ('persona_name', models.CharField(blank=True, max_length=128, verbose_name='имя Steam')),
                ('avatar_url', models.URLField(blank=True, max_length=500, verbose_name='аватар Steam')),
                ('profile_url', models.URLField(blank=True, max_length=500, verbose_name='ссылка Steam')),
                ('rank_tier', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='rank tier')),
                ('mmr_estimate', models.PositiveIntegerField(blank=True, null=True, verbose_name='оценка MMR')),
                ('wins', models.PositiveIntegerField(default=0, verbose_name='победы')),
                ('losses', models.PositiveIntegerField(default=0, verbose_name='поражения')),
                ('recent_matches', models.JSONField(blank=True, default=list, verbose_name='последние матчи')),
                ('stats_updated_at', models.DateTimeField(blank=True, null=True, verbose_name='статистика обновлена')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='steam_account', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'привязанный Steam-аккаунт', 'verbose_name_plural': 'привязанные Steam-аккаунты'},
        ),
    ]
