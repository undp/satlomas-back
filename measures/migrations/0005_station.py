# Generated by Django 3.0.2 on 2020-01-25 13:45

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('measures', '0004_place'),
    ]

    operations = [
        migrations.CreateModel(
            name='Station',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('geom',
                 django.contrib.gis.db.models.fields.PointField(srid=4326)),
                ('metadata',
                 django.contrib.postgres.fields.jsonb.JSONField(blank=True,
                                                                null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('place_id',
                 models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                   to='measures.Place')),
            ],
        ),
    ]
