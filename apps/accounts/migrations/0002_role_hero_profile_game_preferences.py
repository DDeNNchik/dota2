from django.db import migrations, models


def seed_game_catalog(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Hero = apps.get_model('accounts', 'Hero')
    for position, name in enumerate(('Carry', 'Mid', 'Offlane', 'Soft Support', 'Hard Support'), start=1):
        Role.objects.get_or_create(position=position, defaults={'name': name})

    heroes = (
        ('Abaddon', 'abaddon'), ('Axe', 'axe'), ('Bane', 'bane'), ('Bristleback', 'bristleback'),
        ('Centaur Warrunner', 'centaur-warrunner'), ('Chaos Knight', 'chaos-knight'), ('Crystal Maiden', 'crystal-maiden'),
        ('Dazzle', 'dazzle'), ('Death Prophet', 'death-prophet'), ('Disruptor', 'disruptor'), ('Drow Ranger', 'drow-ranger'),
        ('Earthshaker', 'earthshaker'), ('Ember Spirit', 'ember-spirit'), ('Enigma', 'enigma'), ('Faceless Void', 'faceless-void'),
        ('Grimstroke', 'grimstroke'), ('Invoker', 'invoker'), ('Juggernaut', 'juggernaut'), ('Legion Commander', 'legion-commander'),
        ('Lich', 'lich'), ('Lina', 'lina'), ('Lion', 'lion'), ('Luna', 'luna'), ('Magnus', 'magnus'), ('Marci', 'marci'),
        ('Mars', 'mars'), ('Medusa', 'medusa'), ('Mirana', 'mirana'), ('Monkey King', 'monkey-king'), ('Necrophos', 'necrophos'),
        ('Oracle', 'oracle'), ('Pangolier', 'pangolier'), ('Phantom Assassin', 'phantom-assassin'), ('Puck', 'puck'),
        ('Pudge', 'pudge'), ('Queen of Pain', 'queen-of-pain'), ('Razor', 'razor'), ('Rubick', 'rubick'),
        ('Shadow Fiend', 'shadow-fiend'), ('Shadow Shaman', 'shadow-shaman'), ('Slark', 'slark'), ('Sniper', 'sniper'),
        ('Spirit Breaker', 'spirit-breaker'), ('Sven', 'sven'), ('Templar Assassin', 'templar-assassin'), ('Tidehunter', 'tidehunter'),
        ('Tinker', 'tinker'), ('Tiny', 'tiny'), ('Vengeful Spirit', 'vengeful-spirit'), ('Void Spirit', 'void-spirit'),
        ('Warlock', 'warlock'), ('Witch Doctor', 'witch-doctor'), ('Wraith King', 'wraith-king'), ('Zeus', 'zeus'),
    )
    for name, slug in heroes:
        Hero.objects.get_or_create(slug=slug, defaults={'name': name})


def unseed_game_catalog(apps, schema_editor):
    apps.get_model('accounts', 'Hero').objects.all().delete()
    apps.get_model('accounts', 'Role').objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='Hero',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, unique=True, verbose_name='герой')),
                ('slug', models.SlugField(unique=True)),
            ],
            options={'verbose_name': 'герой', 'verbose_name_plural': 'герои', 'ordering': ('name',)},
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=32, unique=True, verbose_name='название')),
                ('position', models.PositiveSmallIntegerField(unique=True, verbose_name='позиция')),
            ],
            options={'verbose_name': 'роль', 'verbose_name_plural': 'роли', 'ordering': ('position',)},
        ),
        migrations.AddField(
            model_name='profile', name='favorite_heroes',
            field=models.ManyToManyField(blank=True, related_name='fans', to='accounts.hero', verbose_name='любимые герои'),
        ),
        migrations.AddField(
            model_name='profile', name='preferred_roles',
            field=models.ManyToManyField(blank=True, related_name='profiles', to='accounts.role', verbose_name='предпочитаемые роли'),
        ),
        migrations.RunPython(seed_game_catalog, unseed_game_catalog),
    ]
