# Generated by Django 3.0.5 on 2020-04-25 19:42

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('stations', '0009_change_meta_on_predictions'),
        ('alerts', '0004_add_fks_on_rule_tables'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='parameterrule',
            unique_together={('user', 'station', 'parameter')},
        ),
    ]
