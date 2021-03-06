# Generated by Django 3.0.5 on 2020-04-26 15:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alerts', '0009_parameterrule_is_absolute'),
    ]

    operations = [
        migrations.RenameField(
            model_name='parameterrule',
            old_name='threshold',
            new_name='valid_max',
        ),
        migrations.RenameField(
            model_name='scoperule',
            old_name='threshold_type',
            new_name='change_type',
        ),
        migrations.RenameField(
            model_name='scoperule',
            old_name='threshold',
            new_name='valid_max',
        ),
        migrations.RenameField(
            model_name='scopetyperule',
            old_name='threshold_type',
            new_name='change_type',
        ),
        migrations.RenameField(
            model_name='scopetyperule',
            old_name='threshold',
            new_name='valid_max',
        ),
        migrations.AddField(
            model_name='parameterrule',
            name='valid_min',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='scoperule',
            name='valid_min',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='scopetyperule',
            name='valid_min',
            field=models.FloatField(default=0),
        ),
    ]
