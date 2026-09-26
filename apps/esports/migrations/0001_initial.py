# Generated manually for the DotaForge esports sources.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ProTeam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='название')),
                ('slug', models.SlugField(unique=True, verbose_name='URL-идентификатор')),
                ('short_name', models.CharField(blank=True, max_length=16, verbose_name='краткое название')),
                ('logo', models.ImageField(blank=True, upload_to='esports/teams/', verbose_name='логотип')),
                ('region', models.CharField(blank=True, max_length=80, verbose_name='регион')),
                ('rating', models.PositiveIntegerField(default=0, verbose_name='рейтинг')),
                ('description', models.TextField(blank=True, max_length=1000, verbose_name='описание')),
            ], options={'ordering': ('-rating', 'name'), 'verbose_name': 'профессиональная команда', 'verbose_name_plural': 'профессиональные команды'},
        ),
        migrations.CreateModel(
            name='Tournament',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='название')), ('slug', models.SlugField(unique=True, verbose_name='URL-идентификатор')),
                ('logo', models.ImageField(blank=True, upload_to='esports/tournaments/', verbose_name='логотип')), ('organizer', models.CharField(blank=True, max_length=120, verbose_name='организатор')),
                ('location', models.CharField(blank=True, max_length=120, verbose_name='место проведения')), ('prize_pool', models.PositiveIntegerField(default=0, verbose_name='призовой фонд, USD')),
                ('format', models.CharField(blank=True, max_length=120, verbose_name='формат')), ('status', models.CharField(choices=[('upcoming', 'Скоро'), ('ongoing', 'Идёт сейчас'), ('completed', 'Завершён')], default='upcoming', max_length=12, verbose_name='статус')),
                ('starts_at', models.DateField(verbose_name='начало')), ('ends_at', models.DateField(verbose_name='окончание')), ('description', models.TextField(blank=True, max_length=2000, verbose_name='описание')),
                ('teams', models.ManyToManyField(blank=True, related_name='tournaments', to='esports.proteam', verbose_name='команды')),
            ], options={'ordering': ('starts_at', 'name'), 'verbose_name': 'турнир', 'verbose_name_plural': 'турниры'},
        ),
        migrations.CreateModel(
            name='ProPlayer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('region', models.CharField(choices=[('americas', 'Америка'), ('europe', 'Европа'), ('se_asia', 'Юго-Восточная Азия'), ('china', 'Китай')], max_length=12, verbose_name='регион рейтинга')),
                ('leaderboard_rank', models.PositiveSmallIntegerField(verbose_name='место в рейтинге')), ('leaderboard_name', models.CharField(blank=True, max_length=128, verbose_name='имя из таблицы Valve')),
                ('team_tag', models.CharField(blank=True, max_length=32, verbose_name='тег команды')), ('sponsor', models.CharField(blank=True, max_length=64, verbose_name='спонсор')),
                ('country_code', models.CharField(blank=True, max_length=2, verbose_name='код страны')), ('account_id', models.PositiveBigIntegerField(blank=True, db_index=True, null=True, verbose_name='OpenDota account ID')),
                ('avatar_url', models.URLField(blank=True, max_length=500, verbose_name='аватар OpenDota')), ('profile_url', models.URLField(blank=True, max_length=500, verbose_name='профиль Steam')),
                ('real_name', models.CharField(blank=True, max_length=128, verbose_name='настоящее имя')), ('rank_tier', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='rank tier')),
                ('leaderboard_rank_opendota', models.PositiveIntegerField(blank=True, null=True, verbose_name='место OpenDota')), ('mmr_estimate', models.PositiveIntegerField(blank=True, null=True, verbose_name='оценка MMR')),
                ('wins', models.PositiveIntegerField(default=0, verbose_name='победы')), ('losses', models.PositiveIntegerField(default=0, verbose_name='поражения')),
                ('source_updated_at', models.DateTimeField(blank=True, null=True, verbose_name='обновлено Valve')), ('opendota_synced_at', models.DateTimeField(blank=True, null=True, verbose_name='обновлено OpenDota')),
                ('last_seen_at', models.DateTimeField(auto_now=True, verbose_name='последний раз в таблице')),
            ], options={'ordering': ('region', 'leaderboard_rank'), 'verbose_name': 'игрок из рейтинга Valve', 'verbose_name_plural': 'игроки из рейтинга Valve'},
        ),
        migrations.AddConstraint(model_name='proplayer', constraint=models.UniqueConstraint(fields=('region', 'leaderboard_rank'), name='unique_valve_leaderboard_slot')),
    ]
