# Generated by Django 3.0.2 on 2020-02-13 17:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('measures', '0005_add_station_code'),
    ]

    operations = [
        migrations.RenameField(
            model_name='place',
            old_name='parent_id',
            new_name='parent',
        ),
        migrations.RenameField(
            model_name='station',
            old_name='place_id',
            new_name='place',
        ),
    ]
