# Generated by Django 3.0.10 on 2020-12-04 19:04

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lomas_changes', '0022_coverageraster'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coverageraster',
            name='cov_rast',
            field=django.contrib.gis.db.models.fields.RasterField(srid=32718),
        ),
    ]
