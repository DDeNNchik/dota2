from django.db import migrations, models


OFFSET_CHOICES = [
    (f'GMT{offset:+d}', f"UTC/GMT{'-' if offset <= 0 else '+'}{abs(offset)}")
    for offset in range(-12, 15)
]


def replace_legacy_timezones(apps, schema_editor):
    Profile = apps.get_model('accounts', 'Profile')
    Profile.objects.filter(timezone='EET').update(timezone='GMT+2')
    Profile.objects.filter(timezone='GMT').update(timezone='GMT+0')


class Migration(migrations.Migration):
    dependencies = [('accounts', '0005_limit_timezones_and_remove_largo')]

    operations = [
        migrations.RunPython(replace_legacy_timezones, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='profile',
            name='timezone',
            field=models.CharField(blank=True, choices=OFFSET_CHOICES, max_length=6, verbose_name='часовой пояс'),
        ),
    ]
