from django.db import migrations, models


class Migration(migrations.Migration):
    """Add Valve/OpenDota fields without removing the former catalog columns.

    Old columns are intentionally retained in SQLite.  This keeps any manually
    entered catalog data recoverable while the application moves to the live
    leaderboard source.
    """

    dependencies = [('esports', '0001_initial')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL("ALTER TABLE esports_proplayer ADD COLUMN region varchar(12) NOT NULL DEFAULT 'europe'"),
                migrations.RunSQL('ALTER TABLE esports_proplayer ADD COLUMN leaderboard_rank integer NOT NULL DEFAULT 0'),
                migrations.RunSQL("ALTER TABLE esports_proplayer ADD COLUMN leaderboard_name varchar(128) NOT NULL DEFAULT ''"),
                migrations.RunSQL("ALTER TABLE esports_proplayer ADD COLUMN team_tag varchar(32) NOT NULL DEFAULT ''"),
                migrations.RunSQL("ALTER TABLE esports_proplayer ADD COLUMN sponsor varchar(64) NOT NULL DEFAULT ''"),
                migrations.RunSQL("ALTER TABLE esports_proplayer ADD COLUMN country_code varchar(2) NOT NULL DEFAULT ''"),
                migrations.RunSQL('ALTER TABLE esports_proplayer ADD COLUMN account_id bigint NULL'),
                migrations.RunSQL("ALTER TABLE esports_proplayer ADD COLUMN avatar_url varchar(500) NOT NULL DEFAULT ''"),
                migrations.RunSQL("ALTER TABLE esports_proplayer ADD COLUMN profile_url varchar(500) NOT NULL DEFAULT ''"),
                migrations.RunSQL("ALTER TABLE esports_proplayer ADD COLUMN real_name varchar(128) NOT NULL DEFAULT ''"),
                migrations.RunSQL('ALTER TABLE esports_proplayer ADD COLUMN rank_tier integer NULL'),
                migrations.RunSQL('ALTER TABLE esports_proplayer ADD COLUMN leaderboard_rank_opendota integer NULL'),
                migrations.RunSQL('ALTER TABLE esports_proplayer ADD COLUMN mmr_estimate integer NULL'),
                migrations.RunSQL('ALTER TABLE esports_proplayer ADD COLUMN source_updated_at datetime NULL'),
                migrations.RunSQL('ALTER TABLE esports_proplayer ADD COLUMN opendota_synced_at datetime NULL'),
                migrations.RunSQL("ALTER TABLE esports_proplayer ADD COLUMN last_seen_at datetime NOT NULL DEFAULT '1970-01-01 00:00:00'"),
                migrations.RunSQL('CREATE INDEX IF NOT EXISTS esports_proplayer_account_id_idx ON esports_proplayer (account_id)'),
            ],
            state_operations=[
                migrations.AddField(model_name='proplayer', name='region', field=models.CharField(choices=[('americas', 'Америка'), ('europe', 'Европа'), ('se_asia', 'Юго-Восточная Азия'), ('china', 'Китай')], default='europe', max_length=12, verbose_name='регион рейтинга')),
                migrations.AddField(model_name='proplayer', name='leaderboard_rank', field=models.PositiveSmallIntegerField(default=0, verbose_name='место в рейтинге')),
                migrations.AddField(model_name='proplayer', name='leaderboard_name', field=models.CharField(blank=True, max_length=128, verbose_name='имя из таблицы Valve')),
                migrations.AddField(model_name='proplayer', name='team_tag', field=models.CharField(blank=True, max_length=32, verbose_name='тег команды')),
                migrations.AddField(model_name='proplayer', name='sponsor', field=models.CharField(blank=True, max_length=64, verbose_name='спонсор')),
                migrations.AddField(model_name='proplayer', name='country_code', field=models.CharField(blank=True, max_length=2, verbose_name='код страны')),
                migrations.AddField(model_name='proplayer', name='account_id', field=models.PositiveBigIntegerField(blank=True, db_index=True, null=True, verbose_name='OpenDota account ID')),
                migrations.AddField(model_name='proplayer', name='avatar_url', field=models.URLField(blank=True, max_length=500, verbose_name='аватар OpenDota')),
                migrations.AddField(model_name='proplayer', name='profile_url', field=models.URLField(blank=True, max_length=500, verbose_name='профиль Steam')),
                migrations.AddField(model_name='proplayer', name='real_name', field=models.CharField(blank=True, max_length=128, verbose_name='настоящее имя')),
                migrations.AddField(model_name='proplayer', name='rank_tier', field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='rank tier')),
                migrations.AddField(model_name='proplayer', name='leaderboard_rank_opendota', field=models.PositiveIntegerField(blank=True, null=True, verbose_name='место OpenDota')),
                migrations.AddField(model_name='proplayer', name='mmr_estimate', field=models.PositiveIntegerField(blank=True, null=True, verbose_name='оценка MMR')),
                migrations.AddField(model_name='proplayer', name='source_updated_at', field=models.DateTimeField(blank=True, null=True, verbose_name='обновлено Valve')),
                migrations.AddField(model_name='proplayer', name='opendota_synced_at', field=models.DateTimeField(blank=True, null=True, verbose_name='обновлено OpenDota')),
                migrations.AddField(model_name='proplayer', name='last_seen_at', field=models.DateTimeField(auto_now=True, verbose_name='последний раз в таблице')),
                migrations.RemoveField(model_name='proplayer', name='average_assists'),
                migrations.RemoveField(model_name='proplayer', name='average_deaths'),
                migrations.RemoveField(model_name='proplayer', name='average_gpm'),
                migrations.RemoveField(model_name='proplayer', name='average_kills'),
                migrations.RemoveField(model_name='proplayer', name='average_xpm'),
                migrations.RemoveField(model_name='proplayer', name='country'),
                migrations.RemoveField(model_name='proplayer', name='full_name'),
                migrations.RemoveField(model_name='proplayer', name='matches_played'),
                migrations.RemoveField(model_name='proplayer', name='nickname'),
                migrations.RemoveField(model_name='proplayer', name='photo'),
                migrations.RemoveField(model_name='proplayer', name='role'),
                migrations.RemoveField(model_name='proplayer', name='slug'),
                migrations.RemoveField(model_name='proplayer', name='team'),
                migrations.RemoveField(model_name='proplayer', name='updated_at'),
                migrations.AlterField(model_name='proplayer', name='leaderboard_rank', field=models.PositiveSmallIntegerField(verbose_name='место в рейтинге')),
                migrations.AlterModelOptions(name='proplayer', options={'ordering': ('region', 'leaderboard_rank'), 'verbose_name': 'игрок из рейтинга Valve', 'verbose_name_plural': 'игроки из рейтинга Valve'}),
                migrations.AddConstraint(model_name='proplayer', constraint=models.UniqueConstraint(fields=('region', 'leaderboard_rank'), name='unique_valve_leaderboard_slot')),
            ],
        ),
    ]
