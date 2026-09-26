from decimal import Decimal
from uuid import uuid4

from django.db import models


def legacy_identifier():
    """Value for a pre-Valve-catalogue column retained in existing SQLite files."""
    return f'legacy-{uuid4().hex}'


class ProTeam(models.Model):
    """A professional team. Tournament data will be synchronised from datdota."""

    name = models.CharField('название', max_length=100, unique=True)
    slug = models.SlugField('URL-идентификатор', unique=True)
    short_name = models.CharField('краткое название', max_length=16, blank=True)
    logo = models.ImageField('логотип', upload_to='esports/teams/', blank=True)
    region = models.CharField('регион', max_length=80, blank=True)
    rating = models.PositiveIntegerField('рейтинг', default=0)
    description = models.TextField('описание', max_length=1_000, blank=True)

    class Meta:
        ordering = ('-rating', 'name')
        verbose_name = 'профессиональная команда'
        verbose_name_plural = 'профессиональные команды'

    def __str__(self):
        return self.name


class ProPlayer(models.Model):
    """A current entry in one of Valve's regional leaderboards.

    Valve does not expose a stable player account ID in its leaderboard response.
    ``account_id`` is therefore populated only after a safe, exact OpenDota match.
    """

    class Region(models.TextChoices):
        AMERICAS = 'americas', 'Америка'
        EUROPE = 'europe', 'Европа'
        SE_ASIA = 'se_asia', 'Юго-Восточная Азия'
        CHINA = 'china', 'Китай'

    region = models.CharField('регион рейтинга', max_length=12, choices=Region.choices)
    leaderboard_rank = models.PositiveSmallIntegerField('место в рейтинге')
    leaderboard_name = models.CharField('имя из таблицы Valve', max_length=128, blank=True)
    team_tag = models.CharField('тег команды', max_length=32, blank=True)
    sponsor = models.CharField('спонсор', max_length=64, blank=True)
    country_code = models.CharField('код страны', max_length=2, blank=True)
    account_id = models.PositiveBigIntegerField('OpenDota account ID', null=True, blank=True, db_index=True)
    avatar_url = models.URLField('аватар OpenDota', max_length=500, blank=True)
    profile_url = models.URLField('профиль Steam', max_length=500, blank=True)
    real_name = models.CharField('настоящее имя', max_length=128, blank=True)
    rank_tier = models.PositiveSmallIntegerField('rank tier', null=True, blank=True)
    leaderboard_rank_opendota = models.PositiveIntegerField('место OpenDota', null=True, blank=True)
    mmr_estimate = models.PositiveIntegerField('оценка MMR', null=True, blank=True)
    wins = models.PositiveIntegerField('победы', default=0)
    losses = models.PositiveIntegerField('поражения', default=0)
    source_updated_at = models.DateTimeField('обновлено Valve', null=True, blank=True)
    opendota_synced_at = models.DateTimeField('обновлено OpenDota', null=True, blank=True)
    last_seen_at = models.DateTimeField('последний раз в таблице', auto_now=True)

    # The first local catalogue had these required columns. They stay hidden
    # solely to keep existing SQLite databases and their old records intact.
    legacy_nickname = models.CharField(max_length=64, unique=True, default=legacy_identifier, editable=False, db_column='nickname')
    legacy_slug = models.SlugField(unique=True, default=legacy_identifier, editable=False, db_column='slug')
    legacy_full_name = models.CharField(max_length=120, blank=True, editable=False, db_column='full_name')
    legacy_photo = models.ImageField(upload_to='esports/players/', blank=True, editable=False, db_column='photo')
    legacy_country = models.CharField(max_length=80, blank=True, editable=False, db_column='country')
    legacy_role = models.CharField(max_length=20, default='mid', editable=False, db_column='role')
    legacy_matches_played = models.PositiveIntegerField(default=0, editable=False, db_column='matches_played')
    legacy_average_kills = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), editable=False, db_column='average_kills')
    legacy_average_deaths = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), editable=False, db_column='average_deaths')
    legacy_average_assists = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), editable=False, db_column='average_assists')
    legacy_average_gpm = models.PositiveIntegerField(default=0, editable=False, db_column='average_gpm')
    legacy_average_xpm = models.PositiveIntegerField(default=0, editable=False, db_column='average_xpm')
    legacy_updated_at = models.DateTimeField(auto_now=True, editable=False, db_column='updated_at')
    legacy_team = models.ForeignKey(ProTeam, on_delete=models.SET_NULL, related_name='+', null=True, blank=True, editable=False, db_column='team_id')

    class Meta:
        ordering = ('region', 'leaderboard_rank')
        constraints = [
            models.UniqueConstraint(fields=('region', 'leaderboard_rank'), name='unique_valve_leaderboard_slot'),
        ]
        verbose_name = 'игрок из рейтинга Valve'
        verbose_name_plural = 'игроки из рейтинга Valve'

    def __str__(self):
        return f'{self.get_region_display()} #{self.leaderboard_rank} — {self.display_name}'

    @property
    def display_name(self):
        return self.leaderboard_name or 'Игрок без публичного имени'

    @property
    def win_rate(self):
        total_games = self.wins + self.losses
        return round((self.wins / total_games) * 100, 1) if total_games else None

    @property
    def rank_label(self):
        if not self.rank_tier:
            return 'Нет данных'
        medals = {1: 'Herald', 2: 'Guardian', 3: 'Crusader', 4: 'Archon', 5: 'Legend', 6: 'Ancient', 7: 'Divine', 8: 'Immortal'}
        return medals.get(self.rank_tier // 10, 'Неизвестно')


class Tournament(models.Model):
    class Status(models.TextChoices):
        UPCOMING = 'upcoming', 'Скоро'
        ONGOING = 'ongoing', 'Идёт сейчас'
        COMPLETED = 'completed', 'Завершён'

    name = models.CharField('название', max_length=150)
    slug = models.SlugField('URL-идентификатор', unique=True)
    logo = models.ImageField('логотип', upload_to='esports/tournaments/', blank=True)
    organizer = models.CharField('организатор', max_length=120, blank=True)
    location = models.CharField('место проведения', max_length=120, blank=True)
    prize_pool = models.PositiveIntegerField('призовой фонд, USD', default=0)
    format = models.CharField('формат', max_length=120, blank=True)
    status = models.CharField('статус', max_length=12, choices=Status.choices, default=Status.UPCOMING)
    starts_at = models.DateField('начало')
    ends_at = models.DateField('окончание')
    description = models.TextField('описание', max_length=2_000, blank=True)
    source_url = models.URLField('источник данных', max_length=500, blank=True)
    teams = models.ManyToManyField(ProTeam, related_name='tournaments', blank=True, verbose_name='команды')

    class Meta:
        ordering = ('starts_at', 'name')
        verbose_name = 'турнир'
        verbose_name_plural = 'турниры'

    def __str__(self):
        return self.name
