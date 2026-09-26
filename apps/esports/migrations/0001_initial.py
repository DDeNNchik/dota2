# Generated manually for the initial DotaForge pro-scene catalog.

import decimal

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
            ], options={'verbose_name': 'профессиональная команда', 'verbose_name_plural': 'профессиональные команды', 'ordering': ('-rating', 'name')},
        ),
        migrations.CreateModel(
            name='Tournament',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('name', models.CharField(max_length=150, verbose_name='название')),
                ('slug', models.SlugField(unique=True, verbose_name='URL-идентификатор')), ('logo', models.ImageField(blank=True, upload_to='esports/tournaments/', verbose_name='логотип')),
                ('organizer', models.CharField(blank=True, max_length=120, verbose_name='организатор')), ('location', models.CharField(blank=True, max_length=120, verbose_name='место проведения')),
                ('prize_pool', models.PositiveIntegerField(default=0, verbose_name='призовой фонд, USD')), ('format', models.CharField(blank=True, max_length=120, verbose_name='формат')),
                ('status', models.CharField(choices=[('upcoming', 'Скоро'), ('ongoing', 'Идёт сейчас'), ('completed', 'Завершён')], default='upcoming', max_length=12, verbose_name='статус')),
                ('starts_at', models.DateField(verbose_name='начало')), ('ends_at', models.DateField(verbose_name='окончание')), ('description', models.TextField(blank=True, max_length=2000, verbose_name='описание')),
                ('teams', models.ManyToManyField(blank=True, related_name='tournaments', to='esports.proteam', verbose_name='команды')),
            ], options={'verbose_name': 'турнир', 'verbose_name_plural': 'турниры', 'ordering': ('starts_at', 'name')},
        ),
        migrations.CreateModel(
            name='ProPlayer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('nickname', models.CharField(max_length=64, unique=True, verbose_name='никнейм')),
                ('slug', models.SlugField(unique=True, verbose_name='URL-идентификатор')), ('full_name', models.CharField(blank=True, max_length=120, verbose_name='полное имя')),
                ('photo', models.ImageField(blank=True, upload_to='esports/players/', verbose_name='фото')), ('country', models.CharField(blank=True, max_length=80, verbose_name='страна')),
                ('role', models.CharField(choices=[('carry', 'Carry'), ('mid', 'Mid'), ('offlane', 'Offlane'), ('soft_support', 'Soft Support'), ('hard_support', 'Hard Support')], max_length=20, verbose_name='роль')),
                ('matches_played', models.PositiveIntegerField(default=0, verbose_name='сыграно карт')), ('wins', models.PositiveIntegerField(default=0, verbose_name='побед')),
                ('losses', models.PositiveIntegerField(default=0, verbose_name='поражений')), ('average_kills', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=5, verbose_name='средние убийства')),
                ('average_deaths', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=5, verbose_name='средние смерти')), ('average_assists', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=5, verbose_name='средние помощи')),
                ('average_gpm', models.PositiveIntegerField(default=0, verbose_name='средний GPM')), ('average_xpm', models.PositiveIntegerField(default=0, verbose_name='средний XPM')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='обновлено')), ('team', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='players', to='esports.proteam', verbose_name='текущая команда')),
            ], options={'verbose_name': 'профессиональный игрок', 'verbose_name_plural': 'профессиональные игроки', 'ordering': ('-wins', '-matches_played', 'nickname')},
        ),
    ]
