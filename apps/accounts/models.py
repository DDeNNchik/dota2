from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def gmt_offset_choices():
    choices = []
    for offset in range(-12, 15):
        sign = '-' if offset <= 0 else '+'
        label = f'UTC/GMT{sign}{abs(offset)}'
        choices.append((f'GMT{offset:+d}', label))
    return tuple(choices)


class Role(models.Model):
    name = models.CharField('название', max_length=32, unique=True)
    position = models.PositiveSmallIntegerField('позиция', unique=True)

    class Meta:
        ordering = ('position',)
        verbose_name = 'роль'
        verbose_name_plural = 'роли'

    def __str__(self):
        return f'Pos {self.position} — {self.name}'


class Hero(models.Model):
    name = models.CharField('герой', max_length=64, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'герой'
        verbose_name_plural = 'герои'

    def __str__(self):
        return self.name


class Profile(models.Model):
    """Optional Dota 2 data kept separate from authentication credentials."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    avatar = models.ImageField('аватар', upload_to='avatars/', blank=True)
    description = models.TextField('о себе', max_length=1_000, blank=True)
    country = models.CharField('страна', max_length=80, blank=True)
    age = models.PositiveSmallIntegerField(
        'возраст', null=True, blank=True, validators=[MinValueValidator(13), MaxValueValidator(120)]
    )
    dota_nickname = models.CharField('Dota 2 никнейм', max_length=64, blank=True)
    steam_id = models.CharField('Steam ID / профиль', max_length=255, blank=True)
    mmr = models.PositiveIntegerField('MMR', null=True, blank=True, validators=[MaxValueValidator(20_000)])
    preferred_roles = models.ManyToManyField(Role, blank=True, related_name='profiles', verbose_name='предпочитаемые роли')
    favorite_heroes = models.ManyToManyField(Hero, blank=True, related_name='fans', verbose_name='любимые герои')
    microphone_available = models.BooleanField('есть микрофон', default=False)
    availability = models.CharField('доступность', max_length=255, blank=True)
    timezone = models.CharField('часовой пояс', max_length=6, choices=gmt_offset_choices(), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'профиль'
        verbose_name_plural = 'профили'

    def __str__(self):
        return f'Профиль {self.user.username}'
