from django.conf import settings
from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    Profile = apps.get_model('accounts', 'Profile')
    database = schema_editor.connection.alias
    profile_user_ids = set(Profile.objects.using(database).values_list('user_id', flat=True))
    Profile.objects.using(database).bulk_create(
        [Profile(user_id=user.pk) for user in User.objects.using(database).exclude(pk__in=profile_user_ids)],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [('accounts', '0002_role_hero_profile_game_preferences')]

    operations = [migrations.RunPython(create_missing_profiles, migrations.RunPython.noop)]
