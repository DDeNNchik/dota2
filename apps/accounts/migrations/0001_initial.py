# Generated manually for DotaForge's initial profile model.

import django.core.validators
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('avatar', models.ImageField(blank=True, upload_to='avatars/', verbose_name='аватар')),
                ('description', models.TextField(blank=True, max_length=1000, verbose_name='о себе')),
                ('country', models.CharField(blank=True, max_length=80, verbose_name='страна')),
                ('age', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(13), django.core.validators.MaxValueValidator(120)], verbose_name='возраст')),
                ('dota_nickname', models.CharField(blank=True, max_length=64, verbose_name='Dota 2 никнейм')),
                ('steam_id', models.CharField(blank=True, max_length=255, verbose_name='Steam ID / профиль')),
                ('mmr', models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(20000)], verbose_name='MMR')),
                ('microphone_available', models.BooleanField(default=False, verbose_name='есть микрофон')),
                ('availability', models.CharField(blank=True, max_length=255, verbose_name='доступность')),
                ('timezone', models.CharField(blank=True, max_length=64, verbose_name='часовой пояс')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'профиль',
                'verbose_name_plural': 'профили',
            },
        ),
    ]
