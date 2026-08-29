from django.db import migrations, models


def normalize_catalog_and_timezones(apps, schema_editor):
    Hero = apps.get_model('accounts', 'Hero')
    Profile = apps.get_model('accounts', 'Profile')

    Hero.objects.filter(slug='largo').delete()
    Profile.objects.filter(timezone__in=('EET', 'EEST', 'Europe/Kyiv', 'Europe/Kiev')).update(timezone='EET')
    Profile.objects.filter(timezone__in=('GMT', 'UTC', 'Etc/GMT')).update(timezone='GMT')
    Profile.objects.exclude(timezone__in=('', 'EET', 'GMT')).update(timezone='')


class Migration(migrations.Migration):
    dependencies = [('accounts', '0004_expand_hero_catalog')]

    operations = [
        migrations.RunPython(normalize_catalog_and_timezones, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='profile',
            name='timezone',
            field=models.CharField(blank=True, choices=[('EET', 'EET — киевское время'), ('GMT', 'GMT — Greenwich Mean Time')], max_length=3, verbose_name='часовой пояс'),
        ),
    ]
