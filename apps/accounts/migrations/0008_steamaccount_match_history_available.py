from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0007_steamaccount')]

    operations = [
        migrations.AddField(
            model_name='steamaccount',
            name='match_history_available',
            field=models.BooleanField(blank=True, null=True, verbose_name='история матчей доступна'),
        ),
    ]
