# Generated by Django 3.0.2 on 2020-01-27 15:42

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stations', '0003_add_lat_lon_to_station'),
    ]

    operations = [
        migrations.AlterField(
            model_name='place',
            name='geom',
            field=django.contrib.gis.db.models.fields.PolygonField(blank=True,
                                                                   null=True,
                                                                   srid=4326),
        ),
        migrations.AlterField(
            model_name='place',
            name='parent_id',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='stations.Place'),
        ),
    ]