# Generated by Django 3.0.6 on 2020-05-15 00:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lomas_changes', '0017_auto_20200507_2025'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='raster',
            name='extent_geom',
        ),
    ]
