# Generated by Django 3.0.6 on 2020-05-25 02:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alerts', '0016_create_user_profiles'),
    ]

    operations = [
        migrations.AddField(
            model_name='scoperule',
            name='is_absolute',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='scopetyperule',
            name='is_absolute',
            field=models.BooleanField(default=False),
        ),
    ]
