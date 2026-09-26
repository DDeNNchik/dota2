from decimal import Decimal
from uuid import uuid4

from django.db import migrations, models


def legacy_identifier():
    return f'legacy-{uuid4().hex}'


class Migration(migrations.Migration):
    dependencies = [('esports', '0002_valve_leaderboard_players')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(model_name='proplayer', name='legacy_nickname', field=models.CharField(db_column='nickname', default=legacy_identifier, editable=False, max_length=64, unique=True)),
                migrations.AddField(model_name='proplayer', name='legacy_slug', field=models.SlugField(db_column='slug', default=legacy_identifier, editable=False, unique=True)),
                migrations.AddField(model_name='proplayer', name='legacy_full_name', field=models.CharField(blank=True, db_column='full_name', editable=False, max_length=120)),
                migrations.AddField(model_name='proplayer', name='legacy_photo', field=models.ImageField(blank=True, db_column='photo', editable=False, upload_to='esports/players/')),
                migrations.AddField(model_name='proplayer', name='legacy_country', field=models.CharField(blank=True, db_column='country', editable=False, max_length=80)),
                migrations.AddField(model_name='proplayer', name='legacy_role', field=models.CharField(db_column='role', default='mid', editable=False, max_length=20)),
                migrations.AddField(model_name='proplayer', name='legacy_matches_played', field=models.PositiveIntegerField(db_column='matches_played', default=0, editable=False)),
                migrations.AddField(model_name='proplayer', name='legacy_average_kills', field=models.DecimalField(db_column='average_kills', decimal_places=2, default=Decimal('0.00'), editable=False, max_digits=5)),
                migrations.AddField(model_name='proplayer', name='legacy_average_deaths', field=models.DecimalField(db_column='average_deaths', decimal_places=2, default=Decimal('0.00'), editable=False, max_digits=5)),
                migrations.AddField(model_name='proplayer', name='legacy_average_assists', field=models.DecimalField(db_column='average_assists', decimal_places=2, default=Decimal('0.00'), editable=False, max_digits=5)),
                migrations.AddField(model_name='proplayer', name='legacy_average_gpm', field=models.PositiveIntegerField(db_column='average_gpm', default=0, editable=False)),
                migrations.AddField(model_name='proplayer', name='legacy_average_xpm', field=models.PositiveIntegerField(db_column='average_xpm', default=0, editable=False)),
                migrations.AddField(model_name='proplayer', name='legacy_updated_at', field=models.DateTimeField(auto_now=True, db_column='updated_at', editable=False)),
                migrations.AddField(model_name='proplayer', name='legacy_team', field=models.ForeignKey(blank=True, db_column='team_id', editable=False, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to='esports.proteam')),
            ],
        ),
    ]
