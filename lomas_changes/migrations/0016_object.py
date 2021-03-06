# Generated by Django 3.0.6 on 2020-05-07 18:40

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('lomas_changes', '0015_auto_20200506_0230'),
    ]

    operations = [
        migrations.CreateModel(
            name='Object',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_type', models.CharField(blank=True, max_length=8, null=True)),
                ('geom', django.contrib.gis.db.models.fields.PolygonField(srid=4326)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='lomas_changes.Period')),
            ],
            options={
                'unique_together': {('period', 'object_type')},
            },
        ),
    ]
