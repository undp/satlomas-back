# Generated by Django 3.0.5 on 2020-04-28 00:14

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('lomas_changes', '0009_add_created_updated_fields_to_coverage_measurements'),
    ]

    operations = [
        migrations.CreateModel(
            name='Raster',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField()),
                ('name', models.CharField(max_length=80)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('area_geom', django.contrib.gis.db.models.fields.PolygonField(srid=4326)),
                ('extra_fields', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='lomas_changes.Period')),
            ],
            options={
                'unique_together': {('slug', 'period')},
            },
        ),
    ]
