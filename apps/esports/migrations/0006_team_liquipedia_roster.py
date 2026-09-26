from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('esports', '0005_tournament_source_url')]

    operations = [
        migrations.AddField(
            model_name='proteam', name='logo_url',
            field=models.URLField(blank=True, max_length=500, verbose_name='логотип Liquipedia'),
        ),
        migrations.AddField(
            model_name='proteam', name='source_url',
            field=models.URLField(blank=True, max_length=500, verbose_name='страница Liquipedia'),
        ),
        migrations.CreateModel(
            name='ProTeamMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nickname', models.CharField(max_length=128, verbose_name='игровой ник')),
                ('real_name', models.CharField(blank=True, max_length=128, verbose_name='имя')),
                ('role', models.CharField(blank=True, max_length=32, verbose_name='позиция')),
                ('photo_url', models.URLField(blank=True, max_length=500, verbose_name='фото Liquipedia')),
                ('source_url', models.URLField(blank=True, max_length=500, verbose_name='страница Liquipedia')),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='roster', to='esports.proteam')),
            ],
            options={'ordering': ('sort_order', 'nickname'), 'verbose_name': 'игрок профессиональной команды', 'verbose_name_plural': 'игроки профессиональной команды'},
        ),
        migrations.AddConstraint(
            model_name='proteammember',
            constraint=models.UniqueConstraint(fields=('team', 'nickname'), name='unique_pro_team_member_nickname'),
        ),
    ]
