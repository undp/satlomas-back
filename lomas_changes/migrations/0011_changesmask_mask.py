# Generated by Django 3.0.5 on 2020-04-28 02:24

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('lomas_changes', '0010_raster'),
    ]

    operations = [
        migrations.CreateModel(
            name='Mask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mask_type', models.CharField(blank=True, max_length=32, null=True)),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(srid=4326)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='lomas_changes.Period')),
            ],
            options={
                'unique_together': {('period', 'mask_type')},
            },
        ),
        migrations.CreateModel(
            name='ChangesMask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mask', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='lomas_changes.Mask')),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='lomas_changes.Period')),
            ],
            options={
                'unique_together': {('period', 'mask')},
            },
        ),
    ]
