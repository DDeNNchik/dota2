from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('esports', '0004_alter_proplayer_legacy_nickname_and_more')]

    operations = [
        migrations.AddField(
            model_name='tournament',
            name='source_url',
            field=models.URLField(blank=True, max_length=500, verbose_name='источник данных'),
        ),
    ]
